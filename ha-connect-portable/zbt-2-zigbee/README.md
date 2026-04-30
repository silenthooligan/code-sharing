# Home Assistant Connect ZBT-2 — Portable Zigbee (community)

Custom WiFi-portable firmware for the ZBT-2 ESP32-S3 USB controller in
Zigbee role. Mirrors the official ZWA-2 portable approach for the ZBT-2
hardware, which Nabu Casa hasn't shipped portable firmware for yet.

The EFR32MG24 stays on its factory **Zigbee NCP** firmware — no
SiLabs-side reflash needed for the Zigbee role. The ESP32-S3 runs
ESPHome with [`oxan/esphome-stream-server`](https://github.com/oxan/esphome-stream-server)
which exposes the EFR32 UART as raw TCP on port 6638. ZHA connects
via `socket://<host>:6638`.

> **Note on `serial_proxy` vs `stream_server`:** ESPHome 2026.3.0 added
> `serial_proxy` (encrypted ESPHome native API) which is the *prettier*
> path on paper — but as of HA 2026.4.x the auto-discovery glue from
> `serial_proxy` to ZHA isn't firing, and ZHA's manual flow only
> accepts `socket://`-style URLs. `stream_server` exposes the UART as
> plain TCP, which ZHA accepts directly. We pick the path that ships
> today; expect this to switch back to `serial_proxy` once the upstream
> discovery glue lands.

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

After hard-reset the dongle joins WiFi within ~10s, exposes raw TCP
on port 6638, and announces via mDNS. Subsequent updates go OTA via
`esphome run zbt-2-zigbee.yaml --device <hostname>.local`.

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

1. **(Optional but recommended) Settings → Devices & Services → Add
   Integration → ESPHome.** Enter the device hostname or IP. This
   surfaces diagnostic sensors (WiFi signal, IP address) under the
   ESPHome integration. The ZHA path is independent.

2. **Settings → Devices & Services → Add Integration → ZHA → Manually
   enter your settings:**
   - Radio type: **EZSP** (Silicon Labs EmberZNet)
   - Serial port: `socket://<device-ip>:6638`
   - Baudrate: `460800`
   - Flow control: `software`

   ZHA forms a fresh Zigbee network. (You're not migrating an existing
   network — Zigbee re-pair is per-device.)

3. **Add Zigbee devices** via ZHA's add-device UI. Each device's
   pairing gesture varies (button-hold, magnet swipe, paddle taps).

## Hardware reference

| ESP32-S3 GPIO | EFR32MG24 pin | Function |
|---|---|---|
| 14 | UART RX | UART TX (host → radio) |
| 13 | UART TX | UART RX (host ← radio) |
| 4  | RESETn  | Radio reset (active LOW, open-drain) |
| 10 | PA6     | Radio bootloader trigger (active LOW) |

UART runs at **460,800 baud, 8N1**.

Pinout source: [`NabuCasa/zwave-esp-bridge` branch `puddly/zbt2-final`](https://github.com/NabuCasa/zwave-esp-bridge/tree/puddly/zbt2-final).

## Why no encryption?

`stream_server` is a separate, plain-TCP listener that doesn't go
through ESPHome's encrypted native API. Raw TCP on `:6638` is ZHA's
only entry point; encryption would need to be configured in socat /
ZHA / zigpy.

This is fine in practice if your IoT VLAN is firewalled (only your HA
host can reach `:6638`), which is good hygiene for IoT anyway.

The ESPHome `api:` block stays enabled (no encryption) so HA's ESPHome
integration can still discover the diagnostic sensors. The two
listeners are independent: ESPHome native API on `:6053`, raw Zigbee
UART on `:6638`.
