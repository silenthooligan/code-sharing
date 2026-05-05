# Legacy: stream_server (raw TCP) variant

This is the previous ZBT-2 Zigbee firmware that exposes the EFR32MG24
UART as a raw TCP listener on port 6638 via
[oxan/esphome-stream-server](https://github.com/oxan/esphome-stream-server).
ZHA connects to it via `socket://<host>:6638`.

The primary [`../zbt-2-zigbee.yaml`](../zbt-2-zigbee.yaml) at the parent
directory now uses ESPHome's first-party `serial_proxy` instead. Pick
this legacy variant only if one of the following applies:

- **HA < 2026.5.** The `esphome-hass://` URL handler that `serial_proxy`
  needs is in `homeassistant/components/esphome/serial_proxy.py` from
  HA 2026.5 forward. Earlier HA releases have no way to consume a
  serial_proxy stream.
- **You haven't applied the bellows Python 3.14 / EZSP-over-TCP fixes.**
  Stock `bellows==0.49.1` (the one HA 2026.5.0b2 ships) breaks before
  EZSP startup completes in either transport. Track upstream merge:
  [zigpy/bellows#720](https://github.com/zigpy/bellows/pull/720). Until
  it lands you'd need to vendor the patched bellows into your HA image
  for either transport to work, but `serial_proxy` is more sensitive
  (the EOF-during-handshake fix is what keeps the encrypted noise tunnel
  alive across init).

`stream_server` will not gain new features here. Once #720 ships and HA
2026.5 cuts to `:stable`, the canonical path is the parent directory's
`serial_proxy` config.

## Bring-up (legacy)

Same as the parent directory, but ZHA's serial port is
`socket://<device-ip>:6638` (or `socket://<hostname>.local:6638`),
baudrate 460800, flow control software.
