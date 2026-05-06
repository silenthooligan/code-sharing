# Home Assistant Connect ZBT-2 - Portable Zigbee (community)

Custom WiFi-portable firmware for the ZBT-2 ESP32-S3 USB controller in
Zigbee role. Mirrors the official ZWA-2 portable approach for the ZBT-2
hardware, which Nabu Casa hasn't shipped portable firmware for yet.

The EFR32MG24 stays on its factory **Zigbee NCP** firmware. No SiLabs-side
reflash needed for the Zigbee role. The ESP32-S3 runs ESPHome with
[`serial_proxy`](https://esphome.io/components/serial_proxy/) (2026.3.0+),
which transports the EFR32 UART inside the encrypted ESPHome native API
on port 6053. ZHA reaches the radio via:

```
esphome-hass://esphome/<esphome_config_entry_id>?port_name=MG24%20Zigbee%20NCP
```

HA 2026.5+ enumerates the proxy in ZHA's serial-port picker; older HA
releases that lack the `esphome-hass://` URL handler should use the
[`legacy-stream-server/`](legacy-stream-server/) variant instead.

**Verified end-to-end:** ZHA forms a fresh mesh on this dongle, IAS-Zone
battery-powered end devices and mains-powered routers join via
permit-join, the device interview completes, and ongoing attribute
reports flow into HA. Validated against HA 2026.5.0b2 and a vendored
bellows patch (see "Status & dependencies" below).

## Status & dependencies

Two upstream gates determine whether this works on a stock HA install:

1. **Home Assistant >= 2026.5.** Adds `homeassistant/components/esphome/serial_proxy.py`
   (the `esphome-hass://` URL handler that registers with `serialx`) and
   the ZHA serial-port picker. Earlier HA versions can't consume a
   `serial_proxy` stream and need the [`legacy-stream-server/`](legacy-stream-server/)
   variant.
2. **Patched bellows.** Stock `bellows==0.49.1` (what HA 2026.5.0b2 ships)
   breaks on the Python 3.14 + EZSP-over-TCP combo with symptoms like
   `'NoneType' object can't be awaited`, `Attempted to use a closed event
   loop`, dropped reset frames during NCP startup, and indefinite ZHA
   retry loops. Tracked at [zigpy/bellows#720](https://github.com/zigpy/bellows/pull/720).
   Until that merges and reaches a HA release, vendor the patched bellows
   into your HA image:
   ```dockerfile
   ARG HA_TAG=2026.5.0b2
   FROM ghcr.io/home-assistant/home-assistant:${HA_TAG}
   RUN pip install --no-deps --force-reinstall \
       https://github.com/silenthooligan/bellows/archive/refs/heads/fix/python-3.14-ezsp-tcp.tar.gz
   ```

If you're on HA <= 2026.4 (no `esphome-hass://`), use the
[`legacy-stream-server/`](legacy-stream-server/) variant. It bypasses both
gates by exposing raw TCP on a separate listener, which ZHA accepts via
`socket://` directly.

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
$EDITOR secrets.yaml      # set wifi_ssid/password, api_encryption_key, ota_password

# 3. Compile + flash
esphome compile zbt-2-zigbee.yaml
cd .esphome/build/home-assistant-zbt-2-zigbee/.pioenvs/home-assistant-zbt-2-zigbee
esptool --port /dev/ttyACM0 --chip esp32s3 \
    --before usb-reset --after hard-reset --baud 460800 \
    write-flash -z --flash-size detect \
    0x0     bootloader.bin \
    0x8000  partitions.bin \
    0x9000  ota_data_initial.bin \
    0x10000 firmware.bin
```

After hard-reset the dongle joins WiFi within ~10s and announces over
mDNS. Subsequent updates go OTA via `esphome run zbt-2-zigbee.yaml
--device <hostname>.local`.

> Tip: `esphome upload <yaml>` does NOT recompile; it flashes whatever's
> in `.esphome/build/<name>/.pioenvs/<name>/firmware.bin`. Two YAMLs that
> share the same `esphome.name:` will fight over the build dir. Use
> `esphome run` (always recompiles) when switching between sibling YAMLs.

## Optional: refresh the EFR32 Zigbee firmware

ZBT-2s ship with Zigbee NCP. To bump to the latest:

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

1. **Settings -> Devices & Services -> Add Integration -> ESPHome.**
   Enter the device hostname or IP. Provide the `api_encryption_key` from
   your `secrets.yaml`. Capture the resulting config entry's `entry_id`
   (visible in `.storage/core.config_entries`, or via the websocket
   `config/config_entries/get_entries` call) for step 2's manual URL
   form. The integration also surfaces diagnostic sensors (WiFi signal,
   IP address).

2. **Settings -> Devices & Services -> Add Integration -> ZHA.**

   On HA 2026.5+, the ESPHome serial proxy named "MG24 Zigbee NCP"
   appears in the serial-port picker; just select it.

   On older HA (with the bellows patch from "Status & dependencies"),
   use manual entry:
   - Radio type: **EZSP** (Silicon Labs EmberZNet)
   - Serial port: `esphome-hass://esphome/<esphome_entry_id>?port_name=MG24%20Zigbee%20NCP`
   - Baudrate: `460800`
   - Flow control: `software`

   ZHA forms a fresh Zigbee network on first add. (You're not migrating
   an existing network. Zigbee re-pair is per-device.)

3. **Add Zigbee devices** via ZHA's add-device UI. Each device's pairing
   gesture varies (button-hold, magnet swipe, paddle taps).

## Migrating from the legacy `stream_server` variant

If you started with [`legacy-stream-server/zbt-2-zigbee.yaml`](legacy-stream-server/zbt-2-zigbee.yaml)
and want to swap to `serial_proxy` without re-pairing devices:

1. OTA-flash the new YAML over the existing dongle (same `esphome.name:`
   so it's a drop-in firmware swap on the same device).
2. The new firmware boots with the encrypted API enabled. HA's existing
   ESPHome integration entry needs the `api_encryption_key` set: trigger
   its **Reconfigure** flow and enter the key. Otherwise the integration
   stays in `state: loaded` but with unavailable entities, and ZHA hits
   `cannot_connect` against the proxy.
3. Delete the existing ZHA config entry and create a new one with the
   `esphome-hass://` URL. ZHA does NOT support reconfiguring the radio
   path in-place (`supports_reconfigure: false`). On the new entry's
   setup-strategy step, use **Advanced -> Reuse settings**, NOT
   "Recommended" (which would form a fresh network and force re-pair).
   With "Reuse settings", the existing `zigbee.db` is honored and devices
   auto-rejoin within ~30s.

## Hardware reference

| ESP32-S3 GPIO | EFR32MG24 pin | Function |
|---|---|---|
| 14 | UART RX | UART TX (host -> radio) |
| 13 | UART TX | UART RX (host <- radio) |
| 4  | RESETn  | Radio reset (active LOW, open-drain) |
| 10 | PA6     | Radio bootloader trigger (active LOW) |

UART runs at **460,800 baud, 8N1**.

Pinout source: [`NabuCasa/zwave-esp-bridge` branch `puddly/zbt2-final`](https://github.com/NabuCasa/zwave-esp-bridge/tree/puddly/zbt2-final).
