# 🧠 The Code Vault

![Ideas](https://img.shields.io/badge/ideas-infinite-blueviolet.svg) ![Status](https://img.shields.io/badge/status-active-success.svg) ![License](https://img.shields.io/badge/license-MIT-green.svg) [![GitHub](https://img.shields.io/badge/GitHub-silenthooligan%2Fcode--sharing-black?logo=github)](https://github.com/silenthooligan/code-sharing)

> **A collection of reverse engineering tools, automation scripts, and digital experiments.**

Welcome to my digital workbench. This repository is a home for code that solves interesting problems, breaks through "impossible" barriers, or just makes life a little bit easier. From reverse-engineering obscure file formats to automating mundane tasks, this is where the magic happens.

---

## 🌟 Featured Projects

### [🛰️ Home Assistant Connect ZBT-2 — Portable WiFi Firmware](./ha-connect-zbt-2-portable)
**Take the ZBT-2 off USB.**
Community ESPHome firmware that puts the Nabu Casa ZBT-2 (Zigbee + Thread) on Wi-Fi instead of USB, plus a CLI flashing helper that doesn't need Chrome's Web Serial. Mirrors the [official ZWA-2 portable firmware](https://github.com/esphome/zwa-2) for the ZBT-2 hardware, which Nabu Casa hasn't officially published yet.
*   **Tech Stack**: ESPHome `serial_proxy`, esptool, universal-silabs-flasher, Python.
*   **Key Feature**: CLI bootloader-entry via the magic-baudrate `cmd>` trick — no browser required.

### [📖 FlipHTML5 Liberator](./fliphtml5-liberator)
**Break through the "Protected" wall.**
A robust tool designed to decrypt and download FlipHTML5 books, even those protected by complex WebAssembly (WASM) encryption and nested obfuscation.
*   **Tech Stack**: Python, Node.js, WASM Reverse Engineering.
*   **Key Feature**: Hybrid decoding architecture that patches Emscripten binaries on the fly.

### [📡 Cyberdrop-DL GUI](./cyberdrop-dl-gui)
**The Visual Downloader.**
A modern, web-based graphical interface for the powerful `cyberdrop-dl` tool, featuring live progress tracking and Docker support.
*   **Tech Stack**: Python, Streamlit, Docker.
*   **Key Feature**: Real-time log parsing and visual feedback loop.

---

## 📂 Repository Structure

The vault is organized by project. Each folder is a self-contained world with its own documentation and requirements.

| Project | Description | Status |
| :--- | :--- | :--- |
| **fliphtml5-liberator** | Universal downloader for protected FlipHTML5 books. | ✅ Stable |
| **cyberdrop-dl-gui** | Web-based GUI for Cyberdrop-DL. | ✅ Stable |
| **ha-connect-zbt-2-portable** | ZBT-2 over Wi-Fi (community fill-in until Nabu Casa ships official). | 🧪 Experimental |
| *(More coming soon)* | *Watch this space for new experiments.* | 🚧 Planned |

---

## 💡 Philosophy

Code should be:
1.  **Useful**: Solves a real problem.
2.  **Robust**: Handles edge cases and weird errors gracefully.
3.  **Creative**: Finds a way when the front door is locked.

---

## 🤝 Contributing

Got a crazy idea? Found a bug in the matrix?
Feel free to open an issue or submit a PR. I'm always looking for new challenges and collaborators.

---

*"Start by doing what's necessary; then do what's possible; and suddenly you are doing the impossible."*
