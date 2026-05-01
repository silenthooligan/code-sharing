import streamlit as st  # type: ignore
import subprocess
import os
import re
import time
import shutil

# --- CONFIGURATION ---
# Public version: BASE_DIR is configurable so you can point it at any
# library root (e.g. /downloads, /mnt/library, ./my_downloads). Subdirs
# under BASE_DIR populate the "Library Category" picker.
BASE_DIR = os.environ.get("DOWNLOAD_DIR", "/downloads")
CONFIG_DIR = os.environ.get("CONFIG_DIR", "/config")
APP_DATA_DIR = os.path.join(CONFIG_DIR, "AppData")

st.set_page_config(
    page_title="Cyberdrop-DL + YT-DLP GUI",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS FOR "PRETTY" UI ---
st.markdown("""
<style>
    .stMetric {
        background-color: #1E1E1E;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #333;
    }
    .stProgress > div > div > div > div {
        background-color: #00ADB5;
    }
    /* Hide the default streamlit menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")

    # Engine Selector
    engine = st.selectbox(
        "Downloader Engine",
        ("Auto (Smart)", "Cyberdrop-DL (Forums/Albums)", "YT-DLP (Video Sites)"),
        index=0,
        help="Select the tool to use. 'Auto' picks the best one based on the URL."
    )

    st.divider()

    # --- FOLDER SELECTION ---
    st.subheader("📂 Save Location")
    if os.path.exists(BASE_DIR):
        subdirs = [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]
        subdirs.sort()
        if "unsorted" not in subdirs:
            subdirs.append("unsorted")
    else:
        subdirs = ["unsorted"]

    selected_base = st.selectbox(
        "Library Category",
        subdirs,
        index=subdirs.index("unsorted") if "unsorted" in subdirs else 0,
    )
    subfolder = st.text_input("Subdirectory (Optional)", placeholder="e.g. artist or models/xxx")

    if subfolder:
        final_download_dir = os.path.join(BASE_DIR, selected_base, subfolder.strip("/"))
    else:
        final_download_dir = os.path.join(BASE_DIR, selected_base)

    st.info(f"Saving to:\n`{final_download_dir}`")

    st.divider()

    # Quick Disk Usage Check
    try:
        total, used, free = shutil.disk_usage(final_download_dir)
    except FileNotFoundError:
        total, used, free = shutil.disk_usage(BASE_DIR) if os.path.exists(BASE_DIR) else (0, 0, 1)

    free_gb = free / (2**30)
    st.metric("Free Storage", f"{free_gb:.2f} GB")

    st.divider()

    ignore_history = st.toggle("Ignore Download History", value=False, help="Re-download files even if they are in the database.")
    force_ipv4 = st.toggle("Force IPv4", value=False, help="Useful if you have IPv6 leaks or VPN issues.")

# --- MAIN LAYOUT ---
st.title("📡 Cyberdrop-DL + YT-DLP GUI")
st.markdown("Enter URLs below (Forums, Cyberdrop, Gofile, YouTube, Vimeo, etc.)")

# URL Input
urls_text = st.text_area(
    "Target URLs (One per line)",
    height=150,
    placeholder="https://example.com/thread/123\nhttps://youtube.com/watch?v=ABC\nhttps://gofile.io/d/ABC",
)

col1, col2 = st.columns([1, 4])
with col1:
    start_btn = st.button("🚀 Start Download", type="primary", use_container_width=True)
with col2:
    status_text = st.empty()


# --- HELPER FUNCTIONS ---
def detect_engine(url_list):
    """
    Heuristic engine pick. We look at the first URL only — if you mix
    video-site URLs with forum/album URLs in one batch, override the
    engine selector instead of relying on Auto.
    """
    video_domains = ["youtube.com", "youtu.be", "vimeo.com", "dailymotion.com", "twitch.tv"]
    first_url = url_list[0].lower()
    if any(x in first_url for x in video_domains):
        return "YT-DLP"
    return "Cyberdrop-DL"


# --- PROCESSING LOGIC ---
if start_btn and urls_text:
    # 1. Setup Environment
    os.makedirs(final_download_dir, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)

    raw_urls = urls_text.strip().splitlines()
    url_list = [u.strip() for u in raw_urls if u.strip()]

    if not url_list:
        st.warning("⚠️ No valid URLs found.")
        st.stop()

    urls_file = os.path.join(CONFIG_DIR, "urls-current.txt")
    with open(urls_file, "w", encoding="utf-8") as f:
        f.write("\n".join(url_list) + "\n")

    # Determine Engine
    if "Auto" in engine:
        selected_engine = detect_engine(url_list)
    elif "YT-DLP" in engine:
        selected_engine = "YT-DLP"
    else:
        selected_engine = "Cyberdrop-DL"

    status_text.info(f"Using Engine: **{selected_engine}**")

    # 2. UI Elements for Live Updates
    st.divider()

    progress_label = st.empty()
    progress_bar = st.progress(0)

    # Metrics Row (Live Counters)
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1: metric_dl = st.metric("Downloaded", "0")
    with m_col2: metric_skip = st.metric("Skipped", "0")
    with m_col3: metric_fail = st.metric("Failed", "0")
    with m_col4: metric_found = st.metric("Found", "0")

    # Logs Expander
    with st.expander("📝 View Raw Terminal Logs", expanded=True):
        log_box = st.empty()

    # 3. Counters
    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "found": 0}
    logs_buffer = []

    # 4. Construct Command
    if selected_engine == "YT-DLP":
        cmd = [
            "yt-dlp",
            "--batch-file", urls_file,
            "-o", f"{final_download_dir}/%(title)s [%(id)s].%(ext)s",
            "--no-mtime",
            "--restrict-filenames",
            "--newline",
            "--no-colors",
        ]
        if ignore_history:
            cmd.append("--force-overwrites")
        else:
            cmd.append("--download-archive")
            cmd.append(os.path.join(CONFIG_DIR, "ytdlp-archive.txt"))

        if force_ipv4:
            cmd.append("--force-ipv4")

    else:
        cmd = [
            "cyberdrop-dl",
            "-i", urls_file,
            "-d", final_download_dir,
            "--appdata-folder", CONFIG_DIR,
            "--download",
            "--ui", "DISABLED",
            "--console-log-level", "20",
        ]

        # Prevent CDL from creating an extra thread/album folder inside
        # an explicitly-chosen subfolder.
        if subfolder:
            cmd.append("--block-download-sub-folders")

        if ignore_history:
            cmd.append("--ignore-history")

    # 5. Run Subprocess
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        progress_label.info(f"⏳ Initializing {selected_engine}...")

        while True:
            if process.stdout is None:
                break
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break

            if line:
                line = line.strip()
                logs_buffer.append(line)
                if len(logs_buffer) > 50:
                    logs_buffer.pop(0)
                log_box.code("\n".join(logs_buffer), language="bash")

                # Live status line
                if "Downloading" in line or "[download]" in line:
                    progress_label.info(f"⬇️ {line[:100]}...")
                    status_text.caption("Running...")
                    progress_bar.progress(int(time.time() * 10) % 100)

                    # yt-dlp current-file percent
                    if "%" in line:
                        match = re.search(r"(\d+\.\d+)%", line)
                        if match:
                            try:
                                pct = float(match.group(1))
                                progress_bar.progress(int(pct))
                            except Exception:
                                pass

                # Counters (heuristic; works for both engines)
                if "File Downloaded" in line:
                    stats["downloaded"] += 1
                    metric_dl.metric("Downloaded", stats["downloaded"])

                if "Skipped" in line or "has already been downloaded" in line:
                    stats["skipped"] += 1
                    metric_skip.metric("Skipped", stats["skipped"])

                if "Failed" in line or "ERROR:" in line:
                    stats["failed"] += 1
                    metric_fail.metric("Failed", stats["failed"])

        # 6. Final Status
        if process.returncode == 0:
            progress_bar.progress(100)
            progress_label.success("✅ Task Complete!")
            st.balloons()
        else:
            progress_label.error(f"❌ Finished with errors (Code {process.returncode})")

    except Exception as e:
        st.error(f"System Error: {str(e)}")

    finally:
        if os.path.exists(urls_file):
            os.remove(urls_file)

elif start_btn and not urls_text:
    st.warning("⚠️ Please paste some URLs first.")
