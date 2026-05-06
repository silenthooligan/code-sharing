# Home Assistant Connect: WiFi Firmware

ESPHome firmware images and reference compose configurations for the
Nabu Casa **ZWA-2** and **ZBT-2** USB radio dongles, providing
network-attached Z-Wave, Zigbee, and Thread radios for Home Assistant
Container deployments.

**Audience:** operators running Home Assistant in a standard Docker /
Compose stack (no HassOS) who want their radio dongles on Wi-Fi rather
than tethered to the host's USB bus.

## Capabilities

| Dongle | Role | Status | ESPHome transport | HA-side integration |
|---|---|---|---|---|
| **ZWA-2** | Z-Wave 800 controller | ✅ Production-validated | `zwave_proxy` (encrypted native API) | Z-Wave JS server v15.15.0+ via `esphome://` |
| **ZBT-2** | Zigbee NCP | ✅ Production-validated | `serial_proxy` (encrypted native API) | ZHA via `esphome-hass://esphome/<entry_id>?port_name=MG24%20Zigbee%20NCP` |
| **ZBT-2** | Thread / OTBR RCP | ✅ Production-validated | `stream_server` (raw TCP :6638) | OTBR via `socat`-bridged pty |

*Nabu Casa's official portable firmware program currently ships images
for the ZWA-2 only; if and when official ZBT-2 images are published,
prefer those. The hardware ships ESP32-S3-ready in all cases. This
repository provides the firmware and integration recipes.*

### Compatibility & dependencies

- **Z-Wave (ZWA-2):** Z-Wave JS server v15.15.0 or newer for the native
  `esphome://` URL handler.
- **Zigbee (ZBT-2):** Home Assistant 2026.5 or newer for the
  `esphome-hass://` URL handler in
  `homeassistant/components/esphome/serial_proxy.py`. Requires the
  bellows fix in [zigpy/bellows#720](https://github.com/zigpy/bellows/pull/720)
  (Python 3.14 + EZSP-over-TCP). For pre-2026.5 / pre-bellows-fix
  systems, use the raw-TCP fallback under
  [`zbt-2-zigbee/legacy-stream-server/`](zbt-2-zigbee/legacy-stream-server/).
- **Thread (ZBT-2):** OpenThread Border Router image with `socat`
  RADIO_URL bridging. The
  [`ghcr.io/ownbee/hass-otbr-docker`](https://github.com/ownbee/hass-otbr-docker)
  image is recommended.

### Validation summary

End-to-end verification for each role on a Home Assistant Container
deployment:

- **Z-Wave (ZWA-2):** S2 Authenticated inclusion, control and state
  round-trips through Z-Wave JS over `esphome://`.
- **Zigbee (ZBT-2):** ZHA mesh formation, permit-join interview
  completion, end-device and router attribute reporting, automation
  triggering.
- **Thread (ZBT-2):** OTBR joins an existing Thread mesh as a secondary
  border router (or forms a new mesh) and routes Matter traffic;
  `socat`-bridged pty remains stable across container restarts.

## Repository layout

```
ha-connect-portable/
├── README.md                         # this document
├── secrets.yaml.example              # WiFi + API/OTA key template
├── enter-esp-bootloader.py           # ESP32-S3 ROM bootloader entry helper
├── zwa-2/
│   ├── README.md                     # ZWA-2 bring-up and Z-Wave JS wiring
│   └── zwa-2.yaml                    # ESPHome config (zwave_proxy, encryption disabled)
├── zbt-2-zigbee/
│   ├── README.md                     # Zigbee bring-up and ZHA wiring
│   ├── zbt-2-zigbee.yaml             # ESPHome config (serial_proxy, encrypted native API)
│   └── legacy-stream-server/         # Pre-2026.5 / pre-bellows-fix fallback (raw TCP)
├── zbt-2-thread/
│   ├── README.md                     # Thread / OTBR bring-up and sidecar wiring
│   └── zbt-2-thread.yaml             # ESPHome config (stream_server, raw TCP)
└── compose-examples/
    ├── zwave-js-server.yml           # ZWA-2 → Z-Wave JS sidecar
    ├── otbr.yml                      # ZBT-2 Thread → OTBR sidecar
    └── full-stack.yml                # HA + matter-server + zwave-js + OTBR reference
```

## Architecture

Each dongle is a dual-MCU design: an **ESP32-S3** USB controller wired
by UART to a **SiLabs EFR32** radio. Stock firmware on the ESP32-S3
implements a USB-CDC bridge, presenting the radio to the host as
`/dev/ttyACM*`. Replacing the ESP32-S3 firmware with an ESPHome image
moves the radio onto the network and removes the USB tether.

The choice of ESPHome proxy component depends on the consumer:

| Component | Transport | Used by |
|---|---|---|
| **`zwave_proxy`** (official) | ESPHome native API (encryption optional) | Z-Wave JS server's `esphome://` URL handler (zwave-js v15.15.0+) |
| **`serial_proxy`** (official, ESPHome 2026.3.0+) | ESPHome native API (encryption recommended) | ZBT-2 Zigbee role. ZHA reaches it via `esphome-hass://` (HA `homeassistant/components/esphome/serial_proxy.py`, 2026.5+). |
| **`stream_server`** ([oxan/esphome-stream-server](https://github.com/oxan/esphome-stream-server)) | Raw TCP on a port | ZBT-2 Thread role (OTBR via `socat`-bridged pty). Also retained as the pre-2026.5 / pre-bellows-fix fallback for the Zigbee role under [`zbt-2-zigbee/legacy-stream-server/`](zbt-2-zigbee/legacy-stream-server/). |

```
HA Container host
┌──────────────────────────────────────────────────────────────────────┐
│  homeassistant   matter-server   zwave-js-server   otbr               │
│        │              │                │             │                │
│        │              │     esphome:// │             │ HTTP :8081     │
│        │ esphome-hass:│ ─────────────► │             │                │
│        │ // (ZHA)     │                │ ─────► ZWA-2│ socat-otbr     │
│        │              │                │             │ -tcp ─────────┐│
└────────┼──────────────┼────────────────┼─────────────┼───────────────┘│
         │ TCP :6053    │                │             │ TCP :6638      │
         │ (encrypted   │                │             │ (raw)          │
         │  native API) │                │             │                │
         ▼              ▼                ▼             ▼                ▼
  ┌──────────────┐  (zigpy native    ┌──────────┐   ┌──────────────┐
  │ ZBT-2        │   socket          │ ZWA-2    │   │ ZBT-2        │
  │ ESPHome      │   client)         │ ESPHome  │   │ ESPHome      │
  │ serial_      │                   │ zwave_   │   │ stream_      │
  │ proxy        │                   │ proxy    │   │ server       │
  └──────┬───────┘                   └────┬─────┘   └──────┬───────┘
         │ UART 460800                    │ UART 115200    │ UART 460800
         ▼                                ▼                ▼
   EFR32MG24                          EFR32ZG23        EFR32MG24
   Zigbee NCP                         Z-Wave 800     OpenThread RCP
```

Both ZBT-2 roles share identical hardware; they differ only in EFR32
firmware variant and ESP32-S3 transport selection. The ZBT-2 Zigbee
role and the ZWA-2 both use the encrypted ESPHome native API
(`serial_proxy` and `zwave_proxy` respectively). The ZBT-2 Thread role
retains `stream_server` because mainline OTBR's `RADIO_URL` parser
only accepts `spinel+hdlc+uart://` and has no native `esphome://`
driver.

## Prerequisites

### Host tooling (flashing workstation)

```bash
pipx install esphome esptool universal-silabs-flasher
pipx inject esptool pyserial
```

`pyserial` is injected into the `esptool` venv because the version
bundled with `esptool` does not always match what `esptool`'s
`--before usb-reset` path expects on Linux when re-enumerating the
ESP32-S3 ROM bootloader.

### Hardware

- Nabu Casa ZWA-2 and/or ZBT-2 dongle(s).
- USB-A or USB-C connection on the flashing host (a powered hub is
  fine; the dongle does not need to live in its final deployment
  location during flashing).

### Network

- 2.4 GHz Wi-Fi reachable from the dongle's deployment location.
- A static DHCP reservation for each flashed dongle is recommended;
  the ESPHome native API and `stream_server` references are by IP or
  resolvable hostname, and a churning DHCP lease will require sidecar
  reconfiguration each cycle.

### Home Assistant version floors

| Role | Floor |
|---|---|
| Z-Wave (ZWA-2) | Z-Wave JS server v15.15.0+ |
| Zigbee (ZBT-2) | HA 2026.5+ with the bellows patch from [zigpy/bellows#720](https://github.com/zigpy/bellows/pull/720); legacy fallback available |
| Thread (ZBT-2) | OTBR image with `socat` RADIO_URL bridging (e.g. ownbee/hass-otbr-docker) |

### Compose stack

Home Assistant Container deployment (no HassOS). Per-role sidecars are
listed in the [Sidecar containers](#sidecar-containers) section.

## Flashing procedure

The procedure is the same for all three dongles, with one optional
EFR32 reflash step that applies only to the Thread role.

### Stage 1: Bench prep

Connect the dongle to the flashing host. Confirm enumeration:

```bash
ls -l /dev/serial/by-id/ | grep -i 'Nabu_Casa'
```

A factory dongle enumerates as `usb-Nabu_Casa_ZWA-2_*-if00` or
`usb-Nabu_Casa_ZBT-2_*-if00`. If nothing appears, check `dmesg` for
USB enumeration errors before proceeding.

### Stage 2: One-time host setup

If you have not previously installed the toolchain on this host, run
the [Host tooling](#host-tooling-flashing-workstation) commands above.

### Stage 3: Optional EFR32 reflash (Thread role only)

For the **ZBT-2 Thread role only**, the EFR32MG24 must run the
OpenThread RCP firmware variant. While the dongle still has the stock
USB-CDC bridge:

```bash
universal-silabs-flasher \
    --device /dev/serial/by-id/usb-Nabu_Casa_ZBT-2_*-if00 \
    --bootloader-reset rts_dtr \
    flash --firmware zbt2_openthread_rcp_*.gbl
```

The flasher leaves the EFR32 in its application slot; the ESP32-S3
USB-CDC bridge remains intact for the next stage. Skip this stage for
the ZWA-2 and the ZBT-2 Zigbee role; both use the factory EFR32
firmware.

### Stage 4: Enter ESP32-S3 ROM bootloader

The stock NabuCasa USB-CDC bridge does not expose GPIO0 to esptool's
auto-reset, so the ROM bootloader is entered via a baud-rate
sequence (see [The magic-baudrate trick](#the-magic-baudrate-trick)
for protocol details). Run:

```bash
./enter-esp-bootloader.py /dev/ttyACM0
```

Successful entry causes the device to disconnect and re-enumerate as
`Espressif ESP32-S3` (`303a:0009`) or `Espressif USB JTAG/serial debug
unit` (`303a:1001`). Confirm with:

```bash
lsusb | grep -E '303a:(0009|1001)'
```

If the device re-enumerates but esptool subsequently reports
`No serial data received`, see the CDC-ACM rebind workaround under
[Operational considerations](#operational-considerations).

### Stage 5: Configure secrets

Populate `secrets.yaml` with WiFi and API/OTA keys:

```bash
cd zwa-2/   # or zbt-2-zigbee/ or zbt-2-thread/
cp ../secrets.yaml.example secrets.yaml
$EDITOR secrets.yaml
```

`secrets.yaml.example` documents each required field. At minimum: WiFi
SSID, WiFi PSK, ESPHome API encryption key (`openssl rand -base64 32`),
and OTA password.

### Stage 6: Compile and flash

```bash
esphome compile zwa-2.yaml   # adjust filename per directory

cd .esphome/build/<name>/.pioenvs/<name>/
esptool --port /dev/ttyACM0 --chip esp32s3 \
    --before usb-reset --after hard-reset --baud 460800 \
    write-flash -z --flash-size detect \
    0x0     bootloader.bin \
    0x8000  partitions.bin \
    0x9000  ota_data_initial.bin \
    0x10000 firmware.bin
```

On success, esptool reports `Hash of data verified` for each segment
and the dongle reboots into the ESPHome firmware.

### Stage 7: Verify deployment

Confirm the dongle has joined Wi-Fi and is reachable:

```bash
esphome logs <name>.yaml          # streams logs over the network
ping <hostname>.local             # mDNS, or use the static reservation
```

The logs should show successful API client connections once the
sidecar (Z-Wave JS, ZHA, or OTBR) is configured to consume the
proxy stream. See [Sidecar containers](#sidecar-containers).

Each `zwa-2/`, `zbt-2-zigbee/`, and `zbt-2-thread/` directory carries
a role-specific README with additional detail on sidecar
configuration and EFR32 firmware sourcing.

## The magic-baudrate trick

The stock NabuCasa USB-CDC bridge firmware does not expose GPIO0
through DTR/RTS, so esptool's auto-reset cannot trigger the ROM
bootloader directly. The bridge does, however, listen for a sequence
of port opens at specific baud rates that places the firmware into
command mode:

| Dongle | Sequence | cmd> baud | Source |
|---|---|---|---|
| ZWA-2 | 150 → 300 → **600** | 600 | [zwave-esp-bridge `master`](https://github.com/NabuCasa/zwave-esp-bridge) |
| ZBT-2 | 150 → 300 → **1200** | 1200 | [zwave-esp-bridge `puddly/zbt2-final`](https://github.com/NabuCasa/zwave-esp-bridge/tree/puddly/zbt2-final) |

Sending `BE` on the resulting prompt reboots the ESP32-S3 into the ROM
bootloader. The [`enter-esp-bootloader.py`](enter-esp-bootloader.py)
helper auto-detects which sequence applies and issues the command.
After it completes, the device re-enumerates as `Espressif ESP32-S3`
(`303a:0009`) or `Espressif USB JTAG/serial debug unit` (`303a:1001`),
and esptool can flash via `--before usb-reset`.

Reference implementation: [home-assistant/zwa2-toolbox](https://github.com/home-assistant/zwa2-toolbox)
`src/lib/esp-utils.ts`.

## Hardware reference

All three dongles share the same ESP32-S3 ↔ EFR32 wiring (verified
against Nabu Casa's published firmware sources):

| ESP32-S3 GPIO | EFR32 pin | Function |
|---|---|---|
| 14 | UART RX | UART TX (host → radio) |
| 13 | UART TX | UART RX (host ← radio) |
| 4 | RESETn | Radio reset (active LOW, open-drain) |
| 10 | PA6 | Radio bootloader trigger (active LOW) |

UART parameters: **115,200 baud** for ZWA-2, **460,800 baud** for
ZBT-2 (both 8N1).

Pinout source: [`NabuCasa/zwave-esp-bridge`](https://github.com/NabuCasa/zwave-esp-bridge),
both `master` and `puddly/zbt2-final` branches.

## Sidecar containers

Each role pairs with a specific consumer on the Home Assistant
Container host:

| Role | Container | Connection to dongle |
|---|---|---|
| Z-Wave (ZWA-2) | [`ghcr.io/kpine/zwave-js-server`](https://github.com/kpine/zwave-js-server-docker) | `esphome://<host>` (built-in zwave-js v15.15.0+ driver) |
| Zigbee (ZBT-2) | None (ZHA is built into Home Assistant) | `esphome-hass://esphome/<entry_id>?port_name=MG24%20Zigbee%20NCP` (encrypted native API via HA's esphome integration). Legacy raw-TCP path: `socket://<host>:6638` from `stream_server`. |
| Thread (ZBT-2) | [`ghcr.io/ownbee/hass-otbr-docker`](https://github.com/ownbee/hass-otbr-docker) | `NETWORK_DEVICE=<host>:6638` → built-in `socat-otbr-tcp` → `/tmp/ttyOTBR` |

Ready-to-deploy compose snippets are provided under
[`compose-examples/`](compose-examples/). The full-stack reference
covers all three dongles alongside Home Assistant and matter-server.

## Operational considerations

- **ZWA-2 RF region defaults to 11 (`USA Long Range End Device`).**
  Inclusion mode appears to run normally but devices never join. The
  background RSSI on all four channels remains at the noise floor
  (~-103 dBm) throughout inclusion. Override with
  `RF_REGION=USA (Long Range)` (or `Europe`, `ANZ`, etc., as
  appropriate to your locale) in the kpine zwave-js-server
  environment. This is the most frequently-encountered initial
  symptom.

- **Z-Wave JS does not implement ESPHome's noise-protocol encryption.**
  Connection attempts fail with `read ECONNRESET`. The ZWA-2 YAML in
  this repository ships an `api:` block with no `encryption:` child;
  isolate the dongle at the network layer instead. Reference:
  [home-assistant/addons#4195](https://github.com/home-assistant/addons/issues/4195).

- **OpenThread Border Router has no `esphome://` driver.** Mainline
  OTBR's `RADIO_URL` parser accepts only `spinel+hdlc+uart://`. The
  Thread role therefore exposes the EFR32 UART via `stream_server`
  (raw TCP) on the dongle, with `socat` (built into the ownbee image)
  bridging it to a pty on the OTBR side.

- **Proxmox unprivileged LXCs do not expose `/dev/net/tun` by
  default.** `otbr-agent` fails with
  `platformConfigureTunDevice() at netif.cpp:2054: No such file or directory`.
  Add to `/etc/pve/lxc/<CTID>.conf`:

  ```
  lxc.cgroup2.devices.allow: c 10:200 rwm
  lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
  ```

  Then `pct restart <CTID>`. Pass `/dev/net/tun:/dev/net/tun` and add
  `cap_add: NET_ADMIN` on the OTBR container.

- **Stale `OT_FORWARD_INGRESS` rules and ipsets on the host** can
  persist after cycling OTBR containers. A new OTBR fails with
  `Set cannot be destroyed: it is in use by a kernel component`. Clean
  before restarting:

  ```bash
  ip6tables -D FORWARD -o wpan0 -j OT_FORWARD_INGRESS
  ip6tables -F OT_FORWARD_INGRESS && ip6tables -X OT_FORWARD_INGRESS
  for s in otbr-ingress-{deny,allow}-{src,src-swap,dst,dst-swap}; do
    ipset destroy "$s" 2>/dev/null
  done
  ```

- **`Failed to connect to ESP32-S3: No serial data received`** after
  the magic-baudrate trick. The ESP32-S3 is in ROM but Linux's CDC-ACM
  driver has not picked up the re-enumeration cleanly. Force a USB
  rebind:

  ```bash
  BUS_ID=$(basename "$(readlink -f /sys/class/tty/ttyACM0/device/..)")
  echo "$BUS_ID" | sudo tee /sys/bus/usb/drivers/usb/unbind
  sleep 1
  echo "$BUS_ID" | sudo tee /sys/bus/usb/drivers/usb/bind
  sudo chmod a+rw /dev/ttyACM*
  ```

## Credits

This work builds on a stack of upstream contributions:

- **Nabu Casa** for the ZBT-2 and ZWA-2 hardware, the
  [zwave-esp-bridge](https://github.com/NabuCasa/zwave-esp-bridge) ESP32-S3
  USB-CDC firmware (which provided the GPIO pinout and the cmd-mode
  protocol), the [silabs-firmware-builder](https://github.com/NabuCasa/silabs-firmware-builder)
  EFR32 firmware (Zigbee NCP, OpenThread RCP, Z-Wave Controller), and
  [esphome/zwa-2](https://github.com/esphome/zwa-2), the official
  ZWA-2 portable firmware on which this repository's variant is based.
- **[@puddly](https://github.com/puddly)** for the
  `puddly/zbt2-final` branch of zwave-esp-bridge, which documents the
  ZBT-2's ESP32-S3 ↔ EFR32 wiring in code (UART pins, reset and
  bootloader pins, magic-baudrate sequence).
- The **ESPHome team** for [`serial_proxy`](https://esphome.io/components/serial_proxy/)
  (2026.3.0) and [`zwave_proxy`](https://esphome.io/components/zwave_proxy/),
  which enable the Zigbee and Z-Wave roles directly.
- **[oxan](https://github.com/oxan)** for [`esphome-stream-server`](https://github.com/oxan/esphome-stream-server),
  the raw-TCP UART exposure that allows OTBR to consume the EFR32
  stream without ESPHome's native API in the data path.
- **[kpine](https://github.com/kpine)** for [`zwave-js-server-docker`](https://github.com/kpine/zwave-js-server-docker),
  the standalone Z-Wave JS Server image for HA Container.
- **[ownbee](https://github.com/ownbee)** for [`hass-otbr-docker`](https://github.com/ownbee/hass-otbr-docker),
  an HA-Container-friendly OTBR with a built-in `socat-otbr-tcp`
  sidecar that converts `NETWORK_DEVICE=host:port` into a usable pty.
- The [home-assistant/zwa2-toolbox](https://github.com/home-assistant/zwa2-toolbox)
  contributors for the magic-baudrate `cmd>` protocol that enables CLI
  flashing without Web Serial.

## License

[MIT](../LICENSE), same as the rest of this code-sharing repository.
