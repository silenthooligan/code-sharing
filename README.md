# code-sharing

Personal repository of small standalone tools, reverse-engineering
utilities, and integration scripts. Each top-level directory is an
independent project with its own README, dependencies, and license
terms (project-level licenses inherit MIT from this repo unless
otherwise noted).

This is a workshop, not a product portfolio. Projects are published
because they were useful enough to write down and may be useful to
someone else; they are not a service offering.

## Projects

### [ha-connect-portable](./ha-connect-portable)

ESPHome firmware images and reference compose configurations for the
Nabu Casa ZWA-2 and ZBT-2 USB radio dongles. Replaces the stock
USB-CDC bridge on the on-board ESP32-S3 with an ESPHome image so the
radio runs on Wi-Fi instead of being tethered to the Home Assistant
host's USB bus.

Covers all three radio roles: Z-Wave (ZWA-2 via `zwave_proxy`), Zigbee
(ZBT-2 via `serial_proxy`), and Thread / OTBR (ZBT-2 via
`stream_server` plus `socat`-bridged pty). Includes the magic-baudrate
ROM-bootloader entry helper, EFR32 reflash procedure for the Thread
role, and ready-to-deploy compose snippets for `zwave-js-server` and
`hass-otbr-docker`.

Status: production-validated. Targets Home Assistant Container
deployments (no HassOS required).

Stack: ESPHome (`zwave_proxy`, `serial_proxy`, `stream_server`),
esptool, universal-silabs-flasher, kpine/zwave-js-server,
ownbee/hass-otbr-docker.

### [fliphtml5-liberator](./fliphtml5-liberator)

Downloader for FlipHTML5 books. Extracts page manifests and image
assets from public FlipHTML5 deployments and assembles them into a
single PDF.

Two operational modes: a fast path that parses the page list directly
when `config.js` exposes it in the clear, and a fallback path that
runs the book's own Emscripten-compiled `deString.wasm` binary inside
a patched Node.js host environment to decrypt the page manifest. The
WASM path handles the "Protected" / encrypted-config variant of
FlipHTML5 where the page list is hidden inside an obfuscated string.

Stack: Python 3.7+ (`httpx`, `img2pdf`, `Pillow`) for orchestration
and PDF assembly; Node.js for the WASM decoder host environment.

### [cyberdrop-dl-gui](./cyberdrop-dl-gui)

Streamlit web UI that wraps `cyberdrop-dl-patched` and `yt-dlp` behind
a single URL-input form. Routes each pasted URL to the appropriate
backend automatically (yt-dlp for the listed video platforms,
cyberdrop-dl for everything else) and persists download history per
backend so re-runs skip already-fetched content.

Includes a library-style folder picker that surfaces subdirectories of
the configured download root as categories, an optional custom
subfolder, live progress counters parsed from the backend log streams,
and a Docker image bundling `aria2`, `ffmpeg`, `cyberdrop-dl-patched`,
and `yt-dlp`.

Stack: Python 3.12+, Streamlit, Docker, `cyberdrop-dl-patched`,
`yt-dlp`, `aria2`, `ffmpeg`.

## Repository structure

Each project is self-contained:

```
code-sharing/
├── README.md                  # this file
├── LICENSE                    # MIT, applies to all projects unless overridden
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── .github/                   # issue templates, PR template
├── ha-connect-portable/       # ESPHome WiFi firmware for ZWA-2 / ZBT-2
├── fliphtml5-liberator/       # FlipHTML5 book extractor
└── cyberdrop-dl-gui/          # Streamlit UI for cyberdrop-dl + yt-dlp
```

## Contributing

Issues and pull requests are welcome on individual projects. See
[CONTRIBUTING.md](./CONTRIBUTING.md) for the basics and
[CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) for behavioral expectations.
Security-sensitive reports should follow [SECURITY.md](./SECURITY.md)
rather than going through the public issue tracker.

## License

[MIT](./LICENSE), unless a specific project directory ships its own
LICENSE file overriding it.
