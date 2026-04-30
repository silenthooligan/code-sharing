# Home Assistant Connect ZBT-2 — Portable WiFi Firmware

> **Status:** Community / unofficial. As of April 2026 Nabu Casa has shipped
> portable Wi-Fi firmware for the **ZWA-2** ([esphome/zwa-2](https://github.com/esphome/zwa-2))
> but **not yet** for the **ZBT-2**. This repo is a stop-gap that mirrors the
> ZWA-2 approach for the ZBT-2 hardware, plus a CLI flashing helper that works
> without Chrome's Web Serial.
>
> If/when Nabu Casa publishes official portable ZBT-2 firmware, prefer that.

## What this gives you

Take the **Home Assistant Connect ZBT-2** off USB and put it on Wi-Fi. The
EFR32MG24 radio (Zigbee or Thread) talks UART to the onboard ESP32-S3, which
runs ESPHome's [`serial_proxy`](https://esphome.io/components/serial_proxy/)
component and proxies the serial bytes to Home Assistant over the network.

```
            ┌──────────────────────────┐
            │ Home Assistant           │
            │  ─ ZHA  (or)             │
            │  ─ OTBR / Thread         │      esphome://<device-ip>
            └─────────────┬────────────┘
                          │ TCP 6053  (encrypted ESPHome native API)
                          ▼
            ┌──────────────────────────┐
            │ ESP32-S3 (ESPHome)       │
            │  ─ Wi-Fi STA             │
            │  ─ serial_proxy          │
            └─────────────┬────────────┘
                          │ UART 460800 8N1
                          ▼
            ┌──────────────────────────┐
            │ EFR32MG24 (Silicon Labs) │
            │  ─ Zigbee NCP   *or*     │
            │  ─ OpenThread RCP        │
            └──────────────────────────┘
```

The two YAMLs in this repo (`home-assistant-zbt-2-zigbee/` and
`home-assistant-zbt-2-thread/`) are **hardware-identical** — they only
differ in the device name they report to Home Assistant. Pick the one
that matches the radio firmware you've flashed onto the EFR32MG24.

## Hardware reference

The ZBT-2's two MCUs are wired together with a fixed pinout, identical
to the ZWA-2 (verified against
[NabuCasa/zwave-esp-bridge `puddly/zbt2-final`](https://github.com/NabuCasa/zwave-esp-bridge/tree/puddly/zbt2-final)):

| ESP32-S3 GPIO | EFR32MG24 pin    | Direction | Function |
|---------------|------------------|-----------|----------|
| 14            | PA8 (USART0 RX)  | →         | UART TX  |
| 13            | PA7 (USART0 TX)  | ←         | UART RX  |
| 4             | RESETn           | →         | Radio reset (active low, open-drain) |
| 10            | PA6              | →         | Radio bootloader trigger (active low) |

UART runs at **460,800 baud, 8N1**. Hardware flow control between the chips
exists at the EFR32 side but the stock ESP32-S3 firmware doesn't drive
CTS/RTS, so this firmware doesn't either — buffer sizes are bumped instead.

## Prerequisites

```bash
pipx install esphome           # 2026.3.0 or newer (when serial_proxy was added)
pipx install esptool
pipx install universal-silabs-flasher   # only if reflashing the EFR32 radio
pipx inject esptool pyserial   # required by the bootloader-entry helper
```

You'll also need:

- A ZBT-2 with stock Nabu Casa firmware (the one it ships with).
- A user account in the `dialout` group, **or** root for the flash steps:
  ```bash
  sudo usermod -a -G dialout "$USER"   # log out + back in to take effect
  ```

## Three-step bring-up

Plug the ZBT-2 into your computer. It enumerates as `Bus … Device … ID
303a:831a Nabu Casa ZBT-2` on `/dev/ttyACM0` (or similar — check
`ls /dev/serial/by-id/`).

### 1. (Optional) Flash the EFR32 radio with the firmware variant you want

The ZBT-2 ships with **Zigbee NCP** firmware on the EFR32. If you want
Zigbee, skip this step. For Thread/Matter:

```bash
# Get the latest .gbl from
#   https://github.com/NabuCasa/silabs-firmware-builder/releases
wget https://github.com/NabuCasa/silabs-firmware-builder/releases/download/v2026.02.23/zbt2_openthread_rcp_2.7.2.0_GitHub-fb0446f53_gsdk_2025.6.2.gbl

universal-silabs-flasher \
  --device /dev/serial/by-id/usb-Nabu_Casa_ZBT-2_*-if00 \
  --bootloader-reset rts_dtr \
  flash --firmware zbt2_openthread_rcp_2.7.2.0_GitHub-fb0446f53_gsdk_2025.6.2.gbl
```

Verify with `universal-silabs-flasher … probe` — it should report
`SPINEL` (OpenThread) instead of `EZSP` (Zigbee).

### 2. Drop the ESP32-S3 into ROM bootloader

The stock USB-CDC bridge firmware doesn't expose a button or DTR/RTS path
to GPIO0, so esptool can't auto-reset the chip the usual way. **It does
listen for a magic baudrate sequence** (the same trick the official
[home-assistant/zwa2-toolbox](https://github.com/home-assistant/zwa2-toolbox)
web installer uses):

```bash
./enter-esp-bootloader.py /dev/ttyACM0
```

The script opens the port at 150, then 300, then 1200 baud (or 600 for ZWA-2),
keeps the third one open, reads back the `cmd>` prompt, and sends `BE` to
hand off to ROM bootloader. After it returns, the device disconnects and
re-enumerates as `Espressif ESP32-S3` (`303a:0009`) or
`Espressif USB JTAG/serial debug unit` (`303a:1001`).

If your kernel doesn't pick up the new device cleanly (esptool times out
on `Connecting...`), do a USB unbind/rebind:

```bash
BUS_ID=$(basename "$(readlink -f /sys/class/tty/ttyACM0/device/..)")
echo "$BUS_ID" | sudo tee /sys/bus/usb/drivers/usb/unbind
sleep 1
echo "$BUS_ID" | sudo tee /sys/bus/usb/drivers/usb/bind
sudo chmod a+rw /dev/ttyACM*
```

### 3. Compile + flash the ESPHome firmware

```bash
cp secrets.yaml.example home-assistant-zbt-2-zigbee/secrets.yaml
$EDITOR home-assistant-zbt-2-zigbee/secrets.yaml   # fill in WiFi + keys

cd home-assistant-zbt-2-zigbee
esphome compile home-assistant-zbt-2-zigbee.yaml

cd .esphome/build/home-assistant-zbt-2-zigbee/.pioenvs/home-assistant-zbt-2-zigbee
esptool --port /dev/ttyACM0 --chip esp32s3 \
  --before usb-reset --after hard-reset --baud 460800 \
  write-flash -z --flash-size detect \
  0x0     bootloader.bin \
  0x8000  partitions.bin \
  0x9000  ota_data_initial.bin \
  0x10000 firmware.bin
```

(Same steps for the Thread variant — substitute `home-assistant-zbt-2-thread`.)

After the hard-reset, the dongle should join your Wi-Fi within ~10s,
announce itself via mDNS as `home-assistant-zbt-2-zigbee.local` (or
`-thread.local`), and start advertising the ESPHome native API on
TCP 6053. From here on, OTA updates go over Wi-Fi:

```bash
esphome run home-assistant-zbt-2-zigbee.yaml \
  --device home-assistant-zbt-2-zigbee.local
```

## Wiring it into Home Assistant

### Zigbee (ZHA)

1. **Settings → Devices & Services → Add Integration → ESPHome.** Enter the
   device hostname or IP. Paste the API encryption key from `secrets.yaml`
   when prompted. The dongle and its diagnostic sensors appear under the
   ESPHome integration.
2. **Settings → Devices & Services → Add Integration → Zigbee Home
   Automation.** Pick *Manually enter your settings*, set radio type to
   **EZSP**, and enter the serial port path:
   ```
   socket://<device-ip>:6638
   ```
   (Substitute the dongle's actual IP. ZHA's Zigpy library understands
   `socket://` for network-attached coordinators. If your version of
   Zigpy supports the `esphome://` URI directly, that works too.)

### Thread / OTBR

Thread integration over `esphome://` is **less mature** than Z-Wave JS or
ZHA as of HA 2026.4. The two practical paths:

- **Wait for upstream support.** ESPHome's `serial_proxy` is the right
  long-term plumbing; HA's OTBR add-on will eventually accept it directly.
- **`socat` shim today.** Run a `socat` translator on the HA host that
  bridges the `serial_proxy` TCP stream to a virtual `/dev/ttyVMG24` that
  OTBR can open as if it were a real UART. Sketch:
  ```bash
  socat -d -d \
    pty,link=/dev/ttyVMG24,raw,echo=0,user=root,group=dialout,mode=660 \
    tcp:<device-ip>:6638
  ```
  Then point the OTBR add-on at `/dev/ttyVMG24`.

If you crack a clean OTBR-over-`esphome://` setup, please open a PR.

## Troubleshooting

- **`No serial data received` from esptool after the magic sequence.** Do
  the USB unbind/rebind (above) — the kernel sometimes hangs onto the old
  CDC enumeration. Then retry with `--before usb-reset`.
- **`OSError: [Errno 71] Protocol error` from esptool.** You're hitting the
  ESP32-S3's USB-Serial-JTAG ROM endpoint, which doesn't honor
  DTR/RTS. Use `--before usb-reset` (works on USB-Serial-JTAG via USB
  control transfer) or `--before no-reset` after manually putting the
  device into bootloader.
- **The cmd> prompt never appears.** The dongle may already be running
  ESPHome (not stock firmware) — use ESPHome's OTA path instead. Or your
  CDC-ACM driver isn't passing baud-rate changes through cleanly; try a
  different USB port / cable.
- **Stuck dongle** (won't boot at all, USB shows `303a:0009` permanently).
  This is actually a *good* state — ESP32-S3 fell back to ROM download
  mode because there's no valid app. Just (re)flash with esptool.

## Credits

This is built on a stack of other people's hard work:

- **Nabu Casa** for the ZBT-2 and ZWA-2 hardware, the
  [zwave-esp-bridge](https://github.com/NabuCasa/zwave-esp-bridge) ESP32-S3
  USB-CDC firmware (which provided the GPIO pinout and the cmd-mode
  protocol), and the
  [silabs-firmware-builder](https://github.com/NabuCasa/silabs-firmware-builder)
  EFR32 firmware (Zigbee NCP, OpenThread RCP, Z-Wave Controller).
- **[@puddly](https://github.com/puddly)** specifically for the
  `puddly/zbt2-final` branch of zwave-esp-bridge — that's where the
  ZBT-2's ESP32-S3 ↔ EFR32 wiring is documented in code.
- The **ESPHome team** for the [`serial_proxy`](https://esphome.io/components/serial_proxy/)
  component (added in 2026.3.0) and [`zwave_proxy`](https://esphome.io/components/zwave_proxy/)
  (esp32 ↔ Z-Wave JS bridge, the prior art for what we're doing here for
  Zigbee/Thread).
- The
  [home-assistant/zwa2-toolbox](https://github.com/home-assistant/zwa2-toolbox)
  contributors for documenting the magic-baudrate `cmd>` protocol that
  made CLI flashing possible without Web Serial.
- The
  [esphome/zwa-2](https://github.com/esphome/zwa-2) repo for the
  reference ZWA-2 portable YAML that this is structurally cribbed from.

If Nabu Casa ships an official portable ZBT-2 firmware (and they
probably will), please prefer that. This repo's purpose is to unblock
people who want to deploy ZBT-2 over Wi-Fi today.

## License

[MIT](../LICENSE) — same as the rest of this code-sharing repo.
