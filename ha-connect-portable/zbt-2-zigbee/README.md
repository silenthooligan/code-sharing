# Home Assistant Connect ZBT-2 — Portable Zigbee (community)

Custom WiFi-portable firmware for the ZBT-2 ESP32-S3 USB controller in
Zigbee role. Mirrors the official ZWA-2 portable approach for the ZBT-2
hardware, which Nabu Casa hasn't shipped portable firmware for yet.

The EFR32MG24 stays on its factory **Zigbee NCP** firmware — no
SiLabs-side reflash needed for the Zigbee role. The ESP32-S3 runs
ESPHome's official `serial_proxy` component (added 2026.3.0) which
exposes the EFR32 UART through ESPHome's native API. ZHA understands
this directly via its serial_proxy adapter.

## Bring-up

```bash
# 0. Install
pipx install esphome esptool
pipx inject esptool pyserial

# 1. Plug ZBT-2 into your machine via USB-C
#    Drop ESP32-S3 into ROM bootloader (magic-baudrate trick)
../enter-esp-bootloader.py /dev/ttyACM0

# 2. Configure
cp ../secrets.yaml.example secrets.yaml
$EDITOR secrets.yaml

# 3. Compile + flash
esphome compile zbt-2-zigbee.yaml
cd .esphome/build/zbt-2-zigbee/.pioenvs/zbt-2-zigbee
esptool --port /dev/ttyACM0 --chip esp32s3 \
    --before usb-reset --after hard-reset --baud 460800 \
    write-flash -z --flash-size detect \
    0x0     bootloader.bin \
    0x8000  partitions.bin \
    0x9000  ota_data_initial.bin \
    0x10000 firmware.bin
```

After hard-reset the dongle joins WiFi within ~10s. Subsequent updates
go OTA via `esphome run zbt-2-zigbee.yaml --device <hostname>.local`.

## Optional: refresh the EFR32 Zigbee firmware

ZBT-2s ship with Zigbee NCP — keep it. To bump to the latest:

```bash
wget https://github.com/NabuCasa/silabs-firmware-builder/releases/download/v2026.02.23/zbt2_zigbee_ncp_7.5.1.0_None.gbl
universal-silabs-flasher \
    --device /dev/serial/by-id/usb-Nabu_Casa_ZBT-2_*-if00 \
    --bootloader-reset rts_dtr \
    flash --firmware zbt2_zigbee_ncp_7.5.1.0_None.gbl
```

Run this **before** the ESP32-S3 ESPHome flash (while the device still
has the stock USB-CDC bridge firmware which exposes the EFR32 directly).

## Wiring into Home Assistant

No sidecar container needed — ZHA's adapter speaks ESPHome's native API:

1. **Settings → Devices & Services → Add Integration → ESPHome.** Enter
   the device hostname or IP. Paste the API encryption key from
   `secrets.yaml`. The dongle and its diagnostic sensors appear under the
   ESPHome integration.

2. **Settings → Devices & Services → Add Integration → Zigbee Home
   Automation.** Pick *Manually enter your settings*, set radio type to
   **EZSP**, and enter the serial port path:
   ```
   socket://<device-ip>:6638
   ```
   (or `esphome://<hostname>.local` if your Zigpy version supports it
   natively — newer versions do).

## Hardware reference

| ESP32-S3 GPIO | EFR32MG24 pin | Function |
|---|---|---|
| 14 | UART RX | UART TX (host → radio) |
| 13 | UART TX | UART RX (host ← radio) |
| 4  | RESETn  | Radio reset (active LOW, open-drain) |
| 10 | PA6     | Radio bootloader trigger (active LOW) |

UART runs at **460,800 baud, 8N1** (different from ZWA-2's 115,200).

Pinout source: [`NabuCasa/zwave-esp-bridge` branch `puddly/zbt2-final`](https://github.com/NabuCasa/zwave-esp-bridge/tree/puddly/zbt2-final).

## Why ESPHome encryption stays ON for Zigbee

ZHA's `serial_proxy` adapter understands ESPHome's noise-protocol PSK
natively. Unlike the ZWA-2 (which talks to zwave-js-server, which
doesn't), there's no reason to disable it. The Zigbee radio + your
encryption key are both protected end-to-end.
