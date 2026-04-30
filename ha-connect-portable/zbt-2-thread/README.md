# Home Assistant Connect ZBT-2 — Portable Thread / OTBR (community)

Custom WiFi-portable firmware for the ZBT-2 ESP32-S3 USB controller in
Thread Border Router role. The EFR32MG24 runs **OpenThread RCP**
firmware (re-flashed from the factory Zigbee NCP); the ESP32-S3 runs
ESPHome with [`oxan/esphome-stream-server`](https://github.com/oxan/esphome-stream-server)
which exposes the EFR32 UART as raw TCP on port 6638.

Why raw TCP instead of ESPHome's `serial_proxy` (which is what the
Zigbee role uses)? **Mainline OTBR has no `esphome://` driver** — its
RADIO_URL parser only speaks `spinel+hdlc+uart://`. Raw TCP is the
universal lowest-common-denominator that any TCP-aware tool can bridge
into a pty.

## Bring-up

```bash
# 0. Install
pipx install esphome esptool universal-silabs-flasher
pipx inject esptool pyserial

# 1. Plug ZBT-2 into your machine via USB-C — and BEFORE the ESPHome flash,
#    re-flash the EFR32 with OpenThread RCP firmware:
wget https://github.com/NabuCasa/silabs-firmware-builder/releases/download/v2026.02.23/zbt2_openthread_rcp_2.7.2.0_GitHub-fb0446f53_gsdk_2025.6.2.gbl
universal-silabs-flasher \
    --device /dev/serial/by-id/usb-Nabu_Casa_ZBT-2_*-if00 \
    --bootloader-reset rts_dtr \
    flash --firmware zbt2_openthread_rcp_2.7.2.0_GitHub-fb0446f53_gsdk_2025.6.2.gbl

# Verify: should now report SPINEL (not EZSP)
universal-silabs-flasher \
    --device /dev/serial/by-id/usb-Nabu_Casa_ZBT-2_*-if00 \
    --bootloader-reset rts_dtr probe

# 2. Drop ESP32-S3 into ROM bootloader (magic-baudrate trick)
../enter-esp-bootloader.py /dev/ttyACM0

# 3. Configure
cp ../secrets.yaml.example secrets.yaml
$EDITOR secrets.yaml

# 4. Compile + flash ESPHome firmware
esphome compile zbt-2-thread.yaml
cd .esphome/build/zbt-2-thread/.pioenvs/zbt-2-thread
esptool --port /dev/ttyACM0 --chip esp32s3 \
    --before usb-reset --after hard-reset --baud 460800 \
    write-flash -z --flash-size detect \
    0x0     bootloader.bin \
    0x8000  partitions.bin \
    0x9000  ota_data_initial.bin \
    0x10000 firmware.bin
```

After hard-reset the dongle joins WiFi within ~10s and starts listening
for raw TCP on port 6638. Subsequent updates go OTA.

## Sidecar: OTBR

For HA Container deployments, [`ownbee/hass-otbr-docker`](https://github.com/ownbee/hass-otbr-docker)
is the cleanest path. It bundles a `socat-otbr-tcp` service that turns
`NETWORK_DEVICE=<host>:<port>` into a local pty (`/tmp/ttyOTBR`) for
otbr-agent to consume.

```yaml
otbr:
  image: ghcr.io/ownbee/hass-otbr-docker:latest
  container_name: otbr
  restart: unless-stopped
  privileged: true   # IPv6 routing + tun/tap
  network_mode: host # mDNS / SRP multicast on infra side
  devices:
    - /dev/net/tun:/dev/net/tun
  cap_add:
    - NET_ADMIN
  environment:
    - NETWORK_DEVICE=YOUR_ZBT2_THREAD_IP:6638  # this dongle's IP:port
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
    - /your/persist/otbr:/data
```

See [`../compose-examples/otbr.yml`](../compose-examples/otbr.yml) for a
full snippet, or [`../compose-examples/full-stack.yml`](../compose-examples/full-stack.yml).

### Proxmox unprivileged-LXC prereq

Unprivileged LXCs don't expose `/dev/net/tun` by default. Add to
`/etc/pve/lxc/<CTID>.conf` and `pct restart <CTID>`:

```
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
```

Without this, `otbr-agent` fails with `platformConfigureTunDevice() at
netif.cpp:2054: No such file or directory` and exits with code 5.

## Wiring into Home Assistant

1. **Add OTBR integration:** Settings → Devices & Services → Add
   Integration → Open Thread Border Router → URL `http://127.0.0.1:8081`.

2. **Adopt existing Thread credentials (recommended).** If you already
   have a Thread network (from any other Border Router on your LAN),
   HA's `thread` integration probably already knows about it. After
   adding the OTBR integration, HA pushes the existing dataset to your
   new BR automatically. The OTBR will go through child → router state
   on the existing mesh in ~30 seconds. Mark it as preferred via the WS
   API:

   ```python
   # Get dataset_id + your OTBR's BA-ID:
   ws.send({"type": "thread/list_datasets"})       # dataset_id
   curl http://127.0.0.1:8081/node                  # baId
   # Then:
   ws.send({"type": "thread/set_preferred_border_agent",
            "dataset_id": "...",
            "border_agent_id": "...",
            "extended_address": "..."})
   ```

3. **Existing Thread / Matter devices keep working** through the new BR
   automatically — no re-commissioning needed. Multi-OTBR is the design
   intent of Thread; any other Border Routers on your LAN become
   redundant secondary routers on the same mesh.

## Hardware reference

| ESP32-S3 GPIO | EFR32MG24 pin | Function |
|---|---|---|
| 14 | UART RX | UART TX (host → radio) |
| 13 | UART TX | UART RX (host ← radio) |
| 4  | RESETn  | Radio reset (active LOW, open-drain) |
| 10 | PA6     | Radio bootloader trigger (active LOW) |

UART runs at **460,800 baud, 8N1**.

## Why no encryption?

The ESPHome `api:` block keeps encryption optional, but `stream_server`
is a separate, plain-TCP listener that doesn't go through the encrypted
native API at all. Raw TCP on `:6638` is the OTBR's only entry point;
any encryption would need to be configured in socat / OTBR.

This is fine in practice if your IoT VLAN is firewalled (only your HA
host can reach `:6638`), which is good hygiene for IoT anyway.
