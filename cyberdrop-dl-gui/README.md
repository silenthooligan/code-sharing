# 📡 Cyberdrop-DL + YT-DLP GUI

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg) ![License](https://img.shields.io/badge/license-MIT-green.svg) ![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)

> **The Visual Downloader.** A web UI that wraps both [`cyberdrop-dl`](https://github.com/jbsparrow/CyberDropDownloader) (forums, albums, file hosts) and [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) (video sites) and auto-routes URLs to the right engine.

---

## 🚀 Why This Tool?

`cyberdrop-dl` is excellent for forum threads and bulk album hosts; `yt-dlp` is the standard for video sites. They have very different command-line conventions. This GUI gives you **one paste box** for both: paste any mix of URLs, hit start, and the right engine runs for the right links.

### ✨ Features

* **🤖 Dual-engine auto-detect** — YouTube / Vimeo / Dailymotion / Twitch URLs route to `yt-dlp`; everything else goes to `cyberdrop-dl`. Override with the engine selector if you need to.
* **📂 Library-style folder picker** — pick a category subdirectory of your library root, optionally append a custom subfolder. CDL is told *not* to nest its own thread/album folders inside an explicitly-chosen path.
* **🖥️ Web Interface** — clean, dark-mode UI powered by Streamlit.
* **📊 Real-time progress** — yt-dlp current-file percent feeds the progress bar; live counters for downloaded / skipped / failed.
* **🐳 Docker Ready** — image bundles `aria2`, `ffmpeg`, `cyberdrop-dl-patched`, and `yt-dlp`.
* **📋 Batch processing** — paste many URLs at once.

---

## 🛠️ Installation

### Option 1: Docker (recommended)

```bash
git clone https://github.com/silenthooligan/code-sharing.git
cd code-sharing/cyberdrop-dl-gui

docker build -t cyberdrop-dl-gui .

mkdir -p downloads config
docker run -d -p 8501:8501 \
  -v $(pwd)/downloads:/downloads \
  -v $(pwd)/config:/config \
  -e DOWNLOAD_DIR=/downloads \
  -e CONFIG_DIR=/config \
  --name cyberdrop-dl-gui \
  cyberdrop-dl-gui
```

Open <http://localhost:8501>.

> **Library categories:** any subdirectory you create under `DOWNLOAD_DIR` shows up in the **Library Category** dropdown. So `mkdir downloads/photos downloads/videos` gives you those two as picker options on next refresh. The `unsorted` option is always available as a fallback.

### Option 2: Local Python

```bash
git clone https://github.com/silenthooligan/code-sharing.git
cd code-sharing/cyberdrop-dl-gui

# System deps:
#   aria2  — required by cyberdrop-dl
#   ffmpeg — required by yt-dlp for muxed video
sudo apt install aria2 ffmpeg          # or: brew install aria2 ffmpeg

pip install -r requirements.txt

mkdir -p downloads config
export DOWNLOAD_DIR=$(pwd)/downloads
export CONFIG_DIR=$(pwd)/config
streamlit run app.py
```

### Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DOWNLOAD_DIR` | Library root. Subdirs of this populate the Library Category picker. | `/downloads` |
| `CONFIG_DIR` | Where cyberdrop-dl AppData and the yt-dlp archive live. | `/config` |

---

## 📖 Usage

1. **Paste URLs** (one per line). Mixing engines in a single batch isn't supported in *Auto* mode (it picks based on the first URL); use the engine selector to force a choice if needed.
2. **Pick a save location** — Library Category dropdown + optional subdirectory text field.
3. **Toggle settings:**
   * *Ignore Download History* — re-downloads files even if they're in the engine's database/archive.
   * *Force IPv4* — useful with VPNs that leak or break IPv6.
4. **🚀 Start Download** — watch live counters and the raw log expander.

### What each engine handles

| Engine | Auto-routes for | Examples |
| :--- | :--- | :--- |
| **Cyberdrop-DL** (default) | Forums, albums, generic file hosts. [Full list →](https://script-ware.gitbook.io/cyberdrop-dl/reference/supported-websites) | `cyberdrop.me`, `gofile.io`, `bunkr.*`, forum threads |
| **YT-DLP** | Video platforms with playlist/manifest support. [Full list →](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) | `youtube.com`, `youtu.be`, `vimeo.com`, `dailymotion.com`, `twitch.tv` |

---

## 🤝 Credits

Standing on the shoulders of giants.

* **`cyberdrop-dl`** — by [**Jules-WinnfieldX**](https://github.com/Jules-WinnfieldX) (now maintained by [**jbsparrow**](https://github.com/jbsparrow/CyberDropDownloader)).
* **`cyberdrop-dl-patched`** — community fork that tracks site changes; this is what's pinned in the image.
* **`yt-dlp`** — [**yt-dlp/yt-dlp**](https://github.com/yt-dlp/yt-dlp).
* **GUI wrapper** — created for the open-source community.

---

**Happy Archiving!** 💾
