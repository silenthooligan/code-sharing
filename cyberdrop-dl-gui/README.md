# cyberdrop-dl-gui

Streamlit web UI that wraps `cyberdrop-dl-patched` and `yt-dlp` behind
a single URL-input form. Each pasted URL is routed to the appropriate
backend, downloads are streamed live into the UI, and per-backend
download history is persisted to a configurable directory so re-runs
skip already-fetched content.

The application is a single-file Python wrapper (`app.py`); the actual
downloading is performed by the underlying CLI tools invoked as
subprocesses. The wrapper handles URL routing, command construction,
log parsing, and progress reporting.

## Capabilities

| Capability | Status |
|---|---|
| Auto-routing between `cyberdrop-dl` and `yt-dlp` | ✅ First-URL heuristic against a video-domain list |
| Manual engine override | ✅ Sidebar selectbox |
| Library-style folder picker | ✅ Subdirectories of `DOWNLOAD_DIR` populate the category dropdown |
| Optional per-batch subdirectory | ✅ Free-text field appended to the chosen category |
| Cyberdrop-DL nesting suppression | ✅ Passes `--block-download-sub-folders` when a custom subfolder is set |
| Persistent yt-dlp download archive | ✅ `${CONFIG_DIR}/ytdlp-archive.txt` |
| Persistent Cyberdrop-DL AppData | ✅ Via `XDG_CONFIG_HOME=${CONFIG_DIR}` |
| Live progress (yt-dlp percent + counters) | ✅ Parsed from backend stdout |
| Free-storage display | ✅ `shutil.disk_usage` against the resolved save path |
| Container image | ✅ Bundles `aria2`, `ffmpeg`, `cyberdrop-dl-patched`, `yt-dlp`, Streamlit |
| Force IPv4 toggle | ✅ Currently surfaced on yt-dlp only |

## URL routing

Engine selection in `Auto` mode is a first-URL heuristic: if the first
URL in the batch contains any of the substrings below, the entire
batch is sent to `yt-dlp`; otherwise the entire batch is sent to
`cyberdrop-dl`.

| Engine | First-URL match | Reference |
|---|---|---|
| `yt-dlp` | `youtube.com`, `youtu.be`, `vimeo.com`, `dailymotion.com`, `twitch.tv` | [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) |
| `cyberdrop-dl` (default) | Anything else (forums, albums, file hosts) | [cyberdrop-dl supported sites](https://script-ware.gitbook.io/cyberdrop-dl/reference/supported-websites) |

Mixing video-platform URLs with forum/album URLs in a single Auto-mode
batch will misroute the non-matching URLs. For mixed batches, set the
engine explicitly via the sidebar selectbox or split the batch.

## Configuration

The application reads two environment variables. All other state lives
inside `CONFIG_DIR` and is managed by the underlying tools.

| Variable | Description | Default |
|---|---|---|
| `DOWNLOAD_DIR` | Library root. Subdirectories of this path populate the Library Category dropdown. | `/downloads` |
| `CONFIG_DIR` | Holds Cyberdrop-DL `AppData/`, yt-dlp download archive, and the transient batch URL file. | `/config` |

`unsorted` is always present in the category dropdown as a fallback,
even if no subdirectories of `DOWNLOAD_DIR` exist yet.

## Installation

### Docker (recommended)

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

The image is based on `python:3.12-slim` and installs `aria2`,
`ffmpeg`, `cyberdrop-dl-patched`, `streamlit`, and `yt-dlp`. Streamlit
binds to `0.0.0.0:8501`; reach the UI at `http://localhost:8501` (or
the host's IP on the network).

To populate categories: `mkdir downloads/photos downloads/videos`
before refreshing the page.

### Local Python

```bash
git clone https://github.com/silenthooligan/code-sharing.git
cd code-sharing/cyberdrop-dl-gui

# System dependencies:
#   aria2  : required by cyberdrop-dl
#   ffmpeg : required by yt-dlp for muxed output
sudo apt install aria2 ffmpeg          # or: brew install aria2 ffmpeg

pip install -r requirements.txt

mkdir -p downloads config
export DOWNLOAD_DIR=$(pwd)/downloads
export CONFIG_DIR=$(pwd)/config
streamlit run app.py
```

Python 3.12+ is recommended (matches the container base image).

## Usage

1. Paste one URL per line into the **Target URLs** text area.
2. (Optional) Pick a **Library Category** and add a **Subdirectory**.
   The resolved save path is shown in the sidebar info box.
3. (Optional) Toggle:
   - **Ignore Download History.** Re-fetches files already recorded in
     the engine's archive. Maps to `--force-overwrites` for yt-dlp and
     `--ignore-history` for cyberdrop-dl.
   - **Force IPv4.** Currently passed to `yt-dlp` only as
     `--force-ipv4`. Useful when an upstream VPN leaks or breaks IPv6.
4. Click **Start Download.** Live counters (Downloaded / Skipped /
   Failed / Found) update from the backend log stream; the raw log
   tail is visible in the **View Raw Terminal Logs** expander.

## Backend command construction

The wrapper builds explicit argv lists; nothing is shelled out as a
string. The exact commands are:

**yt-dlp:**

```text
yt-dlp \
    --batch-file ${CONFIG_DIR}/urls-current.txt \
    -o "${final_download_dir}/%(title)s [%(id)s].%(ext)s" \
    --no-mtime \
    --restrict-filenames \
    --newline \
    --no-colors \
    [--download-archive ${CONFIG_DIR}/ytdlp-archive.txt | --force-overwrites] \
    [--force-ipv4]
```

**cyberdrop-dl:**

```text
cyberdrop-dl \
    -i ${CONFIG_DIR}/urls-current.txt \
    -d ${final_download_dir} \
    --appdata-folder ${CONFIG_DIR} \
    --download \
    --ui DISABLED \
    --console-log-level 20 \
    [--block-download-sub-folders]   # set when a custom subfolder is in use
    [--ignore-history]
```

`--block-download-sub-folders` is set whenever the user supplies a
custom subdirectory, preventing cyberdrop-dl from creating an
additional thread/album folder underneath an explicitly-chosen path.

## Operational notes

- **Counter parsing is heuristic.** The wrapper increments counters on
  string matches in the backend stdout (`File Downloaded`, `Skipped`,
  `has already been downloaded`, `Failed`, `ERROR:`). If the upstream
  log format changes, the counts will stop tracking. The download
  itself is unaffected.
- **Progress bar is yt-dlp-driven.** The wrapper extracts `(\d+\.\d+)%`
  from yt-dlp's `--newline` log stream. Cyberdrop-dl runs do not
  publish a parseable per-file percent and will show an oscillating
  progress bar based on wall-clock time only.
- **Single-run state.** `${CONFIG_DIR}/urls-current.txt` is written
  per-run and removed in the `finally` block, even if the subprocess
  exits non-zero.
- **Persistent history.** Cyberdrop-DL's database lives in
  `${CONFIG_DIR}/AppData/`; yt-dlp's archive lives in
  `${CONFIG_DIR}/ytdlp-archive.txt`. Both survive container restarts
  when `CONFIG_DIR` is bind-mounted.
- **No authentication on the UI.** Streamlit listens on `0.0.0.0` by
  design. Place behind a reverse proxy with auth if exposing beyond
  localhost or a trusted LAN.

## Credits

- [`cyberdrop-dl`](https://github.com/jbsparrow/CyberDropDownloader)
  by [@Jules-WinnfieldX](https://github.com/Jules-WinnfieldX),
  currently maintained by
  [@jbsparrow](https://github.com/jbsparrow/CyberDropDownloader).
- `cyberdrop-dl-patched`: the community fork pinned in the container
  image; tracks site-handling fixes ahead of upstream releases.
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp).
- [`streamlit`](https://streamlit.io) for the UI runtime.

## License

[MIT](../LICENSE).
