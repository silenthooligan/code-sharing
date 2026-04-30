# Home Assistant Connect — Portable WiFi Firmware

WiFi-portable ESPHome firmware for the Nabu Casa **ZWA-2** and **ZBT-2**
USB radio dongles, plus the docker-compose sidecar wiring (zwave-js-server,
OpenThread Border Router) needed to make them useful in a Home Assistant
**Container** deployment (no HassOS required).

## Status

| Dongle | Role | Upstream availability | This repo |
|---|---|---|---|
| **ZWA-2** | Z-Wave 800 controller | ✅ Official: [`esphome/zwa-2`](https://github.com/esphome/zwa-2) | Variant with two production-tested deltas (encryption-off for Z-Wave JS compat, MAC-suffixed name) |
| **ZBT-2** | Zigbee NCP | ❌ Not yet shipped by Nabu Casa | ESPHome `serial_proxy` — works with ZHA's adapter (HA 2026.3+) |
| **ZBT-2** | Thread / OTBR | ❌ Not yet shipped by Nabu Casa | ESPHome `stream_server` (raw TCP) → bridged to OTBR via `socat` |

**This is a stop-gap.** If Nabu Casa ships official portable firmware for
the ZBT-2, prefer that. The ZBT-2 hardware has the ESP32-S3 already
on-board; this repo just provides the firmware that turns it on. All
three patterns have been verified end-to-end against a Home Assistant
Container deployment — devices included on the Z-Wave network, Thread
nodes paired through HA's own OTBR (joining an existing mesh as a
secondary router, or forming a new one).

## What's in this directory

```
ha-connect-portable/
├── README.md                         # this file
├── secrets.yaml.example              # WiFi + API/OTA key template
├── enter-esp-bootloader.py           # magic-baudrate ROM-bootloader trick
│                                     #   (works for ZBT-2 and ZWA-2)
├── zwa-2/
│   ├── README.md                     # ZWA-2-specific bring-up + Z-Wave JS wiring
│   └── zwa-2.yaml                    # ESPHome config (zwave_proxy, no encryption)
├── zbt-2-zigbee/
│   ├── README.md                     # Zigbee role bring-up + ZHA wiring
│   └── zbt-2-zigbee.yaml             # ESPHome config (serial_proxy, encrypted API)
├── zbt-2-thread/
│   ├── README.md                     # Thread/OTBR bring-up + sidecar wiring
│   └── zbt-2-thread.yaml             # ESPHome config (stream_server, raw TCP)
└── compose-examples/
    ├── zwave-js-server.yml           # ZWA-2 → Z-Wave JS sidecar
    ├── otbr.yml                      # ZBT-2 thread → OTBR sidecar
    └── full-stack.yml                # HA + matter + zwave-js + otbr together
```

## Architecture

Each dongle is dual-MCU: an **ESP32-S3** USB controller wired by UART to
a **SiLabs EFR32** radio. The factory firmware turns the ESP32-S3 into a
USB-CDC bridge so the host sees `/dev/ttyACM*`. Replacing it with ESPHome
puts the dongle on Wi-Fi and frees you from the USB tether.

The right ESPHome component to use depends on what speaks to the radio:

| Component | Transport | Used by |
|---|---|---|
| **`zwave_proxy`** (official) | ESPHome native API (encrypted optional) | Z-Wave JS server's `esphome://` URL handler (zwave-js v15.15.0+) |
| **`serial_proxy`** (official, 2026.3.0+) | ESPHome native API (encrypted optional) | ZHA's serial_proxy adapter |
| **`stream_server`** ([oxan/esphome-stream-server](https://github.com/oxan/esphome-stream-server)) | Raw TCP on a port | Anything that wants plain serial-over-TCP — e.g. OTBR (via socat-bridged pty) |

```
HA Container host
┌──────────────────────────────────────────────────────────────────┐
│  homeassistant   matter-server   zwave-js-server   otbr           │
│        │              │                │             │            │
│        │              │                │ esphome://  │ HTTP :8081 │
│        │              │                │             │            │
│        └─── ESPHome integration (serial_proxy adapter for ZHA) ──┐│
└────────────────────────────────────────────────────────────────┐ ││
                            │                                    │ ││
                            │ Wi-Fi (your IoT VLAN)              │ ││
        ┌───────────────────┼────────────┬───────────────────────┘ ││
        │                   │            │                          ││
        ▼                   ▼            ▼                          ▼▼
  ┌──────────┐        ┌──────────┐ ┌──────────────┐         ┌──────────────┐
  │ ZWA-2    │        │ ZBT-2 #1 │ │ ZBT-2 #2     │         │ ZBT-2 #2     │
  │ ESPHome  │        │ ESPHome  │ │ ESPHome      │ TCP 6638│ ESPHome      │
  │ zwave_   │        │ serial_  │ │ stream_      │ ────────│ stream_      │
  │ proxy    │        │ proxy    │ │ server       │         │ server       │
  └────┬─────┘        └────┬─────┘ └──────┬───────┘         └──────┬───────┘
       │                   │              │                         │
   EFR32ZG23           EFR32MG24        EFR32MG24                 (above)
   Z-Wave 800          Zigbee NCP    OpenThread RCP
```

The ZBT-2 in Thread role is shown twice in the diagram only because the
TCP path goes through `socat-otbr-tcp` (a service inside the OTBR
container) which exposes `/tmp/ttyOTBR` for `otbr-agent` to read as
`spinel+hdlc+uart://`.

## Quick start

For each dongle, three commands:

```bash
# 0. One-time setup
pipx install esphome esptool universal-silabs-flasher
pipx inject esptool pyserial

# 1. (Optional, ZBT-2 Thread only) Reflash the EFR32MG24 with OpenThread
#    RCP firmware while it still has stock USB-CDC bridge:
universal-silabs-flasher \
    --device /dev/serial/by-id/usb-Nabu_Casa_ZBT-2_*-if00 \
    --bootloader-reset rts_dtr \
    flash --firmware zbt2_openthread_rcp_*.gbl

# 2. Drop ESP32-S3 into ROM bootloader (magic-baudrate trick):
./enter-esp-bootloader.py /dev/ttyACM0

# 3. Configure + flash:
cd zwa-2/   # or zbt-2-zigbee/ or zbt-2-thread/
cp ../secrets.yaml.example secrets.yaml
$EDITOR secrets.yaml
esphome compile zwa-2.yaml   # adjust filename per dir
cd .esphome/build/<name>/.pioenvs/<name>/
esptool --port /dev/ttyACM0 --chip esp32s3 \
    --before usb-reset --after hard-reset --baud 460800 \
    write-flash -z --flash-size detect \
    0x0     bootloader.bin \
    0x8000  partitions.bin \
    0x9000  ota_data_initial.bin \
    0x10000 firmware.bin
```

Each `zwa-2/`, `zbt-2-zigbee/`, `zbt-2-thread/` directory has its own
README with the role-specific details.

## The magic-baudrate trick

The stock NabuCasa USB-CDC bridge firmware doesn't expose a button or
DTR/RTS path to the ESP32-S3's GPIO0, so esptool's auto-reset can't
trigger ROM bootloader. **It does listen for a sequence of port opens at
specific baud rates** which puts the firmware into command mode:

| Dongle | Sequence | cmd> baud | Source |
|---|---|---|---|
| ZWA-2 | 150 → 300 → **600** | 600 | [zwave-esp-bridge `master`](https://github.com/NabuCasa/zwave-esp-bridge) |
| ZBT-2 | 150 → 300 → **1200** | 1200 | [zwave-esp-bridge `puddly/zbt2-final`](https://github.com/NabuCasa/zwave-esp-bridge/tree/puddly/zbt2-final) |

Then sending `BE` on the prompt reboots into ROM bootloader. The
[`enter-esp-bootloader.py`](enter-esp-bootloader.py) helper auto-tries
both sequences. After it returns, the device disconnects + re-enumerates
as `Espressif ESP32-S3` (303a:0009) or `Espressif USB JTAG/serial debug
unit` (303a:1001) and esptool can flash via `--before usb-reset`.

Reference: [home-assistant/zwa2-toolbox](https://github.com/home-assistant/zwa2-toolbox)
`src/lib/esp-utils.ts`.

## Hardware reference

All three dongles share the same ESP32-S3 ↔ EFR32 wiring (verified
against Nabu Casa's own firmware sources):

| ESP32-S3 GPIO | EFR32 pin | Function |
|---|---|---|
| 14 | UART RX | UART TX (host → radio) |
| 13 | UART TX | UART RX (host ← radio) |
| 4 | RESETn | Radio reset (active LOW, open-drain) |
| 10 | PA6 | Radio bootloader trigger (active LOW) |

Baud rates: **115,200** for ZWA-2, **460,800** for ZBT-2 (both 8N1).

Pinout source: [`NabuCasa/zwave-esp-bridge`](https://github.com/NabuCasa/zwave-esp-bridge),
both `master` and `puddly/zbt2-final` branches.

## Sidecar containers

For HA Container deployments (no HassOS), each role has a sidecar:

| Role | Container | Talks to dongle via |
|---|---|---|
| Z-Wave (ZWA-2) | [`ghcr.io/kpine/zwave-js-server`](https://github.com/kpine/zwave-js-server-docker) | `esphome://<host>` (built-in) |
| Zigbee (ZBT-2) | *(none — ZHA built into HA)* | `socket://<host>:6638` |
| Thread (ZBT-2) | [`ghcr.io/ownbee/hass-otbr-docker`](https://github.com/ownbee/hass-otbr-docker) | `NETWORK_DEVICE=<host>:6638` → built-in `socat-otbr-tcp` → `/tmp/ttyOTBR` |

See [`compose-examples/`](compose-examples/) for ready-to-use snippets.
The full-stack example covers all three dongles + HA + matter-server.

## Known gotchas

- **ZWA-2 RF region defaults to 11 (`USA Long Range End Device`).**
  Inclusion mode looks like it's running but devices never join — the
  background RSSI on all 4 channels stays at the noise floor (~-103 dBm)
  during inclusion. Override with `RF_REGION=USA (Long Range)` (or
  `Europe`, `ANZ`, etc. per your locale) in the kpine zwave-js-server
  env. This is the single most-confusing first-encounter symptom.

- **Z-Wave JS doesn't speak ESPHome's noise-protocol encryption.**
  Connection fails with `read ECONNRESET`. The ZWA-2 YAML in this repo
  ships `api:` with no `encryption:` block. Mitigate via firewall
  isolation. Issue: [home-assistant/addons#4195](https://github.com/home-assistant/addons/issues/4195).

- **OTBR doesn't have an `esphome://` driver.** Mainline OTBR's
  RADIO_URL parser only speaks `spinel+hdlc+uart://`. We use
  `stream_server` (raw TCP) on the dongle and `socat` (built into the
  ownbee image) on the OTBR side to bridge.

- **Proxmox unprivileged LXCs don't expose `/dev/net/tun` by default.**
  `otbr-agent` fails with `platformConfigureTunDevice() at netif.cpp:2054:
  No such file or directory`. Add to `/etc/pve/lxc/<CTID>.conf`:
  ```
  lxc.cgroup2.devices.allow: c 10:200 rwm
  lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
  ```
  then `pct restart <CTID>`. Pass `/dev/net/tun:/dev/net/tun` and add
  `cap_add: NET_ADMIN` on the OTBR container.

- **Stale `OT_FORWARD_INGRESS` rules + ipsets on the host** if you've
  cycled OTBR containers. New OTBR fails with `Set cannot be destroyed:
  it is in use by a kernel component`. Clean before restarting:
  ```bash
  ip6tables -D FORWARD -o wpan0 -j OT_FORWARD_INGRESS
  ip6tables -F OT_FORWARD_INGRESS && ip6tables -X OT_FORWARD_INGRESS
  for s in otbr-ingress-{deny,allow}-{src,src-swap,dst,dst-swap}; do
    ipset destroy "$s" 2>/dev/null
  done
  ```

- **`Failed to connect to ESP32-S3: No serial data received`** after the
  magic-baudrate trick. The ESP32-S3 is in ROM but Linux's CDC-ACM driver
  hasn't picked up the re-enumeration cleanly. Force a USB rebind:
  ```bash
  BUS_ID=$(basename "$(readlink -f /sys/class/tty/ttyACM0/device/..)")
  echo "$BUS_ID" | sudo tee /sys/bus/usb/drivers/usb/unbind
  sleep 1
  echo "$BUS_ID" | sudo tee /sys/bus/usb/drivers/usb/bind
  sudo chmod a+rw /dev/ttyACM*
  ```

## Credits

This is built on a stack of other people's work:

- **Nabu Casa** for the ZBT-2 + ZWA-2 hardware, the
  [zwave-esp-bridge](https://github.com/NabuCasa/zwave-esp-bridge) ESP32-S3
  USB-CDC firmware (which provided the GPIO pinout and the cmd-mode
  protocol), the [silabs-firmware-builder](https://github.com/NabuCasa/silabs-firmware-builder)
  EFR32 firmware (Zigbee NCP, OpenThread RCP, Z-Wave Controller), and
  [esphome/zwa-2](https://github.com/esphome/zwa-2) — the official
  ZWA-2 portable firmware that this repo's variant is based on.
- **[@puddly](https://github.com/puddly)** specifically for the
  `puddly/zbt2-final` branch of zwave-esp-bridge — that's where the
  ZBT-2's ESP32-S3 ↔ EFR32 wiring is documented in code (UART pins,
  reset/bootloader pins, magic-baudrate sequence).
- The **ESPHome team** for [`serial_proxy`](https://esphome.io/components/serial_proxy/)
  (2026.3.0) and [`zwave_proxy`](https://esphome.io/components/zwave_proxy/),
  which made the Zigbee + Z-Wave roles trivial.
- **[oxan](https://github.com/oxan)** for [`esphome-stream-server`](https://github.com/oxan/esphome-stream-server) —
  the raw-TCP UART exposure that lets OTBR talk to the EFR32 without
  ESPHome's native API in the way.
- **[kpine](https://github.com/kpine)** for [`zwave-js-server-docker`](https://github.com/kpine/zwave-js-server-docker) —
  the standalone Z-Wave JS Server image for HA Container.
- **[ownbee](https://github.com/ownbee)** for [`hass-otbr-docker`](https://github.com/ownbee/hass-otbr-docker) —
  HA-Container-friendly OTBR with a built-in `socat-otbr-tcp` sidecar
  that turns `NETWORK_DEVICE=host:port` into a usable pty.
- The [home-assistant/zwa2-toolbox](https://github.com/home-assistant/zwa2-toolbox)
  contributors for the magic-baudrate `cmd>` protocol that made CLI
  flashing possible without Web Serial.

## License

[MIT](../LICENSE) — same as the rest of this code-sharing repo.
