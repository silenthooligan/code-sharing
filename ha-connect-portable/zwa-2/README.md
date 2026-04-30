# Home Assistant Connect ZWA-2 — Portable (community variant)

A drop-in alternative to the official [`esphome/zwa-2`](https://github.com/esphome/zwa-2)
firmware with two production-tested deviations baked in:

1. **No ESPHome native-API encryption.** Z-Wave JS server doesn't speak the
   noise protocol — connections fail with `read ECONNRESET` if encryption is
   enabled. Mitigate via firewall isolation on the dongle's VLAN.
2. **`name_add_mac_suffix: true`** so multiple instances coexist on the same LAN.

Everything else (pinout, `zwave_proxy`, BT proxy + tracker) is identical to upstream.

## Bring-up

Three steps, ~5 minutes total:

```bash
# 0. Install ESPHome + esptool + pyserial helper
pipx install esphome esptool
pipx inject esptool pyserial

# 1. Plug ZWA-2 into your machine via USB-C
#    Drop ESP32-S3 into ROM bootloader (magic-baudrate trick)
../enter-esp-bootloader.py /dev/ttyACM0

# 2. Configure
cp ../secrets.yaml.example secrets.yaml
$EDITOR secrets.yaml   # WiFi + API/OTA keys

# 3. Compile + flash
esphome compile zwa-2.yaml
cd .esphome/build/zwa-2-portable/.pioenvs/zwa-2-portable
esptool --port /dev/ttyACM0 --chip esp32s3 \
    --before usb-reset --after hard-reset --baud 460800 \
    write-flash -z --flash-size detect \
    0x0     bootloader.bin \
    0x8000  partitions.bin \
    0x9000  ota_data_initial.bin \
    0x10000 firmware.bin
```

After hard-reset, the ZWA-2 joins your Wi-Fi within ~10s and announces via
mDNS as `zwa-2-portable-<mac-suffix>.local`. Subsequent updates go OTA.

## Sidecar: `zwave-js-server`

HA Container doesn't ship a Z-Wave JS Server — it's a separate process.
The kpine image is the standard:

```yaml
zwave-js-server:
  image: ghcr.io/kpine/zwave-js-server:latest
  container_name: zwave-js-server
  restart: unless-stopped
  network_mode: host
  # The kpine entrypoint validates USB_PATH as a character device which
  # esphome:// URLs aren't. Use the `server` subcommand to bypass.
  command: ["server", "esphome://YOUR_ZWA2_IP",
            "--config", "options.js", "--disable-dns-sd"]
  environment:
    # CRITICAL — ZWA-2 ships set to RFRegion 11 ("USA Long Range End Device")
    # which makes it act as an end device and refuse to run inclusion. Override:
    - RF_REGION=USA (Long Range)   # or "Europe", "ANZ", etc.
    - S0_LEGACY_KEY=...             # generate: openssl rand -hex 16 | tr a-f A-F
    - S2_ACCESS_CONTROL_KEY=...
    - S2_AUTHENTICATED_KEY=...
    - S2_UNAUTHENTICATED_KEY=...
    - LR_S2_ACCESS_CONTROL_KEY=...
    - LR_S2_AUTHENTICATED_KEY=...
  volumes:
    - /your/persist/zwave-js:/cache
```

See [`../compose-examples/zwave-js-server.yml`](../compose-examples/zwave-js-server.yml)
for a full snippet, or [`../compose-examples/full-stack.yml`](../compose-examples/full-stack.yml)
for HA + matter-server + zwave-js-server + OTBR all together.

## Wiring into Home Assistant

1. **Settings → Devices & Services → Add Integration → ESPHome.** Enter
   the device hostname or IP. The dongle shows up with diagnostic
   sensors (WiFi RSSI, IP, Bluetooth Proxy switch). No encryption key
   needed since we removed it.

2. **Settings → Devices & Services → Add Integration → Z-Wave JS.**
   *Manually enter your settings* → server URL `ws://localhost:3000`
   (assumes zwave-js-server is on the HA host; adjust for remote).

3. **Inclusion** — add a Z-Wave device from the Z-Wave JS integration UI
   or via the WebSocket API. For S2 devices that don't need PIN entry,
   `inclusion_strategy=2` (Insecure) is the smoothest path; for S2
   Authenticated you'll need to wire up the `grant_security_classes` +
   `validate_dsk_and_enter_pin` event handlers.

## Why no encryption?

ESPHome's native API supports an optional noise-protocol-pre-shared-key
(noise_psk) layer. ZHA and zwave-js's `esphome://` driver have native
support for negotiating that PSK. **Z-Wave JS does NOT** — issue
[home-assistant/addons#4195](https://github.com/home-assistant/addons/issues/4195)
tracks this. Symptoms when encryption is enabled:

```
ZWaveError: Failed to open the serial port: read ECONNRESET (ZW0100)
```

Two paths forward:

- **Disable encryption** (this YAML's choice). Safe iff your dongle is
  reachable only from a tightly-firewalled VLAN. Recommended setup:
  - Dedicate an IoT VLAN
  - Allow only your HA host's IP to reach the dongle's TCP 6053
  - Block dongle → outbound internet

- **Wait for upstream support.** Once Z-Wave JS adds noise-protocol
  support, just paste the encryption block back in and OTA-flash.

## Why the magic-baudrate dance?

The stock NabuCasa USB-CDC bridge firmware (`zwave-esp-bridge`) doesn't
expose a button or DTR/RTS path to the ESP32-S3's GPIO0. esptool's
auto-reset can't trigger the ROM bootloader. The firmware listens for
a sequence of port opens at 150 → 300 → 600 baud, then accepts a `BE`
command on a `cmd>` prompt to hand off to ROM. See
[`../enter-esp-bootloader.py`](../enter-esp-bootloader.py).

Reference implementation: [home-assistant/zwa2-toolbox](https://github.com/home-assistant/zwa2-toolbox)
`src/lib/esp-utils.ts`.

## Hardware reference

| ESP32-S3 GPIO | EFR32ZG23 pin | Function |
|---|---|---|
| 14 | UART RX | UART TX (host → radio) |
| 13 | UART TX | UART RX (host ← radio) |

UART runs at **115,200 baud, 8N1** (different from the ZBT-2's 460,800).

The Z-Wave radio firmware on the EFR32ZG23 ships from Nabu Casa correctly
preinstalled. Unlike the ZBT-2, you do **not** need `universal-silabs-flasher`
to swap the radio firmware — the ESP32-S3 firmware swap is the only step.
