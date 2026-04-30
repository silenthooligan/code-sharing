# Home Assistant Connect ZBT-2 — Portable WiFi Firmware

> **Status:** Community / unofficial. As of April 2026 Nabu Casa has shipped
> portable Wi-Fi firmware for the **ZWA-2** ([esphome/zwa-2](https://github.com/esphome/zwa-2))
> but **not yet** for the **ZBT-2**. This repo is a working stop-gap that
> mirrors the ZWA-2 approach for the ZBT-2 hardware, plus a CLI flashing
> helper that works without Chrome's Web Serial.
>
> The architecture has been proven end-to-end against a Home Assistant
> Container deployment driving an OpenThread Border Router on the dongle's
> Thread radio (Aperture Labs production homelab — Nest Hubs demoted to
> secondary BRs on the same Thread mesh). Issues / PRs welcome.
>
> If/when Nabu Casa publishes official portable ZBT-2 firmware, prefer that.

## What this gives you

Take the **Home Assistant Connect ZBT-2** off USB and put it on Wi-Fi.
The EFR32MG24 radio (Zigbee or Thread) talks UART to the onboard ESP32-S3
which runs ESPHome and proxies the serial bytes over the network.

```
                ┌──────────────────────────────────────────┐
                │ Home Assistant Container                 │
                │   ─ ZHA       (Zigbee role)              │   ←── esphome:// (encrypted API)
                │   ─ otbr-agent + socat-otbr-tcp           │   ←── raw TCP :6638
                │     (ownbee/hass-otbr-docker)            │       │
                └──────────────────────────────────────────┘       │
                              ▲                                    │
                              │ HTTP REST :8081                    │
                              │ (HA `otbr` integration)            │
                                                                   │
                  ┌────────────────────────────────────────────────┘
                  │
                  ▼
                ┌──────────────────────────┐
                │ ZBT-2 ESP32-S3 (ESPHome) │
                │  ─ Wi-Fi STA             │
                │  ─ serial_proxy (Zigbee) │   OR
                │  ─ stream_server (Thread)│
                └─────────────┬────────────┘
                              │ UART 460800 8N1
                              ▼
                ┌──────────────────────────┐
                │ EFR32MG24 (Silicon Labs) │
                │  ─ Zigbee NCP    *or*    │
                │  ─ OpenThread RCP        │
                └──────────────────────────┘
```

The two YAMLs in this repo are **hardware-identical** but use different
ESPHome components for the ESP32-S3 side, because **what consumes the
serial bytes differs by role**:

| Role | YAML | ESPHome component | Why |
|---|---|---|---|
| **Zigbee** | [`home-assistant-zbt-2-zigbee.yaml`](home-assistant-zbt-2-zigbee/home-assistant-zbt-2-zigbee.yaml) | `serial_proxy` (encrypted ESPHome native API) | ZHA understands ESPHome's serial_proxy adapter directly (HA 2026.3+) |
| **Thread / OTBR** | [`home-assistant-zbt-2-thread.yaml`](home-assistant-zbt-2-thread/home-assistant-zbt-2-thread.yaml) | `stream_server` (raw TCP) via [oxan/esphome-stream-server](https://github.com/oxan/esphome-stream-server) | Mainline OTBR's `RADIO_URL` parser only speaks `spinel+hdlc+uart://` — it has no `esphome://` driver. Raw TCP gets bridged into a pty by socat. |

## Hardware reference

The ZBT-2 ESP32-S3 ↔ EFR32MG24 wiring is identical to the ZWA-2 (verified
against [`NabuCasa/zwave-esp-bridge` branch `puddly/zbt2-final`](https://github.com/NabuCasa/zwave-esp-bridge/tree/puddly/zbt2-final)):

| ESP32-S3 GPIO | EFR32MG24 pin    | Direction | Function |
|---------------|------------------|-----------|----------|
| 14            | PA8 (USART0 RX)  | →         | UART TX  |
| 13            | PA7 (USART0 TX)  | ←         | UART RX  |
| 4             | RESETn           | →         | Radio reset (active low, open-drain) |
| 10            | PA6              | →         | Radio bootloader trigger (active low) |

UART runs at **460,800 baud, 8N1**.

## Prerequisites

```bash
pipx install esphome             # 2026.3.0+ (when serial_proxy was added)
pipx install esptool
pipx install universal-silabs-flasher   # only if reflashing the EFR32 radio
pipx inject esptool pyserial      # required by enter-esp-bootloader.py
```

You'll also need:
- A ZBT-2 with stock Nabu Casa firmware.
- A user account in the `dialout` group, **or** root for the flash steps:
  ```bash
  sudo usermod -a -G dialout "$USER"   # log out + back in
  ```

## Three-step bring-up

### 1. (Optional) Flash the EFR32 radio with the firmware variant you want

The ZBT-2 ships with **Zigbee NCP** firmware on the EFR32. For Zigbee,
skip this step. For Thread/Matter, reflash:

```bash
# Latest GBL from https://github.com/NabuCasa/silabs-firmware-builder/releases
wget https://github.com/NabuCasa/silabs-firmware-builder/releases/download/v2026.02.23/zbt2_openthread_rcp_2.7.2.0_GitHub-fb0446f53_gsdk_2025.6.2.gbl

universal-silabs-flasher \
  --device /dev/serial/by-id/usb-Nabu_Casa_ZBT-2_*-if00 \
  --bootloader-reset rts_dtr \
  flash --firmware zbt2_openthread_rcp_2.7.2.0_GitHub-fb0446f53_gsdk_2025.6.2.gbl
```

Verify with `universal-silabs-flasher … probe` — should report `SPINEL`
(OpenThread) instead of `EZSP` (Zigbee).

### 2. Drop the ESP32-S3 into ROM bootloader

Stock USB-CDC bridge firmware doesn't expose a button or DTR/RTS path to
GPIO0, so esptool can't auto-reset. **It does listen for a magic-baudrate
sequence** (the trick the official [home-assistant/zwa2-toolbox](https://github.com/home-assistant/zwa2-toolbox)
web installer uses):

```bash
./enter-esp-bootloader.py /dev/ttyACM0
```

Tries the ZBT-2 sequence (150/300/1200) first, falls back to the ZWA-2
sequence (150/300/600). Reads the `cmd>` prompt, sends `BE`, the device
disconnects + re-enumerates as `Espressif ESP32-S3` (303a:0009) or
`Espressif USB JTAG/serial debug unit` (303a:1001).

If the kernel doesn't pick up the new device cleanly (esptool times out
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
$EDITOR home-assistant-zbt-2-zigbee/secrets.yaml   # WiFi + keys

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

Same steps for the Thread variant — substitute `home-assistant-zbt-2-thread`.

After hard-reset, the dongle joins your Wi-Fi within ~10s and announces
via mDNS as `home-assistant-zbt-2-zigbee.local` (or `-thread.local`).
Subsequent updates go OTA:

```bash
esphome run home-assistant-zbt-2-zigbee.yaml \
  --device home-assistant-zbt-2-zigbee.local
```

## Wiring it into Home Assistant

### Zigbee (ZHA)

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
   (or use the `esphome://<device-ip>` URI if your Zigpy version supports
   it natively).

### Thread / OTBR (HA Container)

This is the path we proved out. The official `openthread/border-router`
image needs a few helping hands; the community-maintained
[`ownbee/hass-otbr-docker`](https://github.com/ownbee/hass-otbr-docker)
is purpose-built for HA Container and bundles a `socat-otbr-tcp` service
that bridges TCP to a local pty automatically.

1. **Add OTBR to your docker-compose:**

   ```yaml
   otbr:
     image: ghcr.io/ownbee/hass-otbr-docker:latest
     container_name: otbr
     restart: unless-stopped
     privileged: true   # IPv6 routing + tun/tap
     network_mode: host # mDNS / SRP multicast on infra side
     devices:
       - /dev/net/tun:/dev/net/tun  # required for wpan0 TUN device
     cap_add:
       - NET_ADMIN
     environment:
       - NETWORK_DEVICE=192.168.40.15:6638  # your ZBT-2 thread IP
       - DEVICE=/tmp/ttyOTBR                # ownbee's socat creates this
       - BAUDRATE=460800
       - FLOW_CONTROL=0
       - BACKBONE_IF=eth0
       - OTBR_REST_PORT=8081
       - OTBR_WEB=0
       - FIREWALL=1
       - NAT64=1
       - THREAD_1_4=1
       - OTBR_LOG_LEVEL=info
     volumes:
       - /your/persist/path:/data
   ```

2. **If running inside a Proxmox unprivileged LXC**, expose `/dev/net/tun`
   to the container. Add to `/etc/pve/lxc/<CTID>.conf` and `pct restart`:
   ```
   lxc.cgroup2.devices.allow: c 10:200 rwm
   lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
   ```
   Without this, `otbr-agent` fails with `platformConfigureTunDevice() …
   No such file or directory` and exits with code 5.

3. **Add HA's OTBR integration:** Settings → Devices & Services → Add
   Integration → Open Thread Border Router → URL `http://127.0.0.1:8081`.

4. **Adopt existing Thread credentials (recommended).** If you already
   have a Thread network (e.g. via Apple Home or a Nest Hub), HA's `thread`
   integration probably already knows about it. After adding the OTBR
   integration, HA pushes the existing dataset to your new BR
   automatically. The OTBR will go through child → router state on the
   existing mesh in ~30 seconds. Mark it as preferred:
   ```bash
   # via WS API:
   #   thread/set_preferred_border_agent
   #     dataset_id   = your dataset id (from thread/list_datasets)
   #     border_agent_id = our BA-ID (from http://127.0.0.1:8081/node baId)
   ```

5. **Lock+ / Matter devices keep working** through the new BR
   automatically — no re-commissioning needed. Multi-OTBR is the design
   intent of Thread.

## Troubleshooting

- **`No serial data received` from esptool after the magic sequence.**
  Do the USB unbind/rebind (above) — the kernel sometimes hangs onto the
  old CDC enumeration. Then retry with `--before usb-reset`.

- **`OSError: [Errno 71] Protocol error` from esptool.** You're on the
  ESP32-S3's USB-Serial-JTAG ROM endpoint, which doesn't honor DTR/RTS.
  Use `--before usb-reset` (works on USB-Serial-JTAG via USB control
  transfer) or `--before no-reset` if the device is already in bootloader.

- **The `cmd>` prompt never appears.** The dongle may already be running
  ESPHome (not stock firmware) — use ESPHome's OTA path instead. Or your
  CDC-ACM driver isn't passing baud-rate changes through; try a different
  USB port / cable.

- **OTBR `otbr-agent exited with code 5` / `platformConfigureTunDevice()
  … No such file or directory`.** Container can't access `/dev/net/tun`.
  Fix the LXC config (above) or run on a host where `/dev/net/tun` is
  available.

- **OTBR `ipset cannot be destroyed: in use by a kernel component`.**
  Stale rules from a previous OTBR container. Stop OTBR, then on the host:
  ```bash
  ip6tables -D FORWARD -o wpan0 -j OT_FORWARD_INGRESS
  ip6tables -F OT_FORWARD_INGRESS && ip6tables -X OT_FORWARD_INGRESS
  for s in otbr-ingress-{deny,allow}-{src,src-swap,dst,dst-swap}; do
    ipset destroy "$s" 2>/dev/null
  done
  ```

- **OTBR is `state=disabled` with `networkName=OpenThread` defaults.**
  HA didn't auto-push your existing dataset. Either re-add the `otbr`
  integration in HA, or push the dataset manually via REST:
  ```bash
  curl -X PUT -H 'Content-Type: text/plain' \
    --data-binary "<TLV-from-thread/get_dataset_tlv>" \
    http://127.0.0.1:8081/node/dataset/active
  curl -X POST -H 'Content-Type: application/json' -d '"enable"' \
    http://127.0.0.1:8081/node/state
  ```

- **`tiocmbic: Inappropriate ioctl for device`.** Harmless. socat tries
  to set modem control lines on a pty that doesn't support them.

## Credits

This is built on a stack of other people's hard work:

- **Nabu Casa** for the ZBT-2 and ZWA-2 hardware, the
  [zwave-esp-bridge](https://github.com/NabuCasa/zwave-esp-bridge) ESP32-S3
  USB-CDC firmware (which provided the GPIO pinout and the cmd-mode
  protocol), and the
  [silabs-firmware-builder](https://github.com/NabuCasa/silabs-firmware-builder)
  EFR32 firmware (Zigbee NCP, OpenThread RCP, Z-Wave Controller).
- **[@puddly](https://github.com/puddly)** specifically for the
  `puddly/zbt2-final` branch of zwave-esp-bridge — that's where the ZBT-2's
  ESP32-S3 ↔ EFR32 wiring is documented in code.
- The **ESPHome team** for [`serial_proxy`](https://esphome.io/components/serial_proxy/)
  (added in 2026.3.0) and [`zwave_proxy`](https://esphome.io/components/zwave_proxy/),
  the prior art for what we're doing here for Zigbee/Thread.
- **[oxan](https://github.com/oxan)** for [`esphome-stream-server`](https://github.com/oxan/esphome-stream-server),
  the raw-TCP UART exposure that lets OTBR talk to the EFR32 without the
  ESPHome native API in the way.
- **[ownbee](https://github.com/ownbee)** for [`hass-otbr-docker`](https://github.com/ownbee/hass-otbr-docker) —
  HA Container OTBR with the `socat-otbr-tcp` sidecar that turns
  `NETWORK_DEVICE=host:port` into a usable `/tmp/ttyOTBR` for `otbr-agent`.
- The [home-assistant/zwa2-toolbox](https://github.com/home-assistant/zwa2-toolbox)
  contributors for documenting the magic-baudrate `cmd>` protocol that
  made CLI flashing possible without Web Serial.
- The [esphome/zwa-2](https://github.com/esphome/zwa-2) repo for the
  reference ZWA-2 portable YAML that this is structurally cribbed from.

If Nabu Casa ships an official portable ZBT-2 firmware (and they probably
will), please prefer that. This repo's purpose is to unblock people who
want to deploy ZBT-2 over Wi-Fi today.

## License

[MIT](../LICENSE) — same as the rest of this code-sharing repo.
