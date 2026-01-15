import streamlit as st
import subprocess
import os
import re
import time
import shutil

# --- CONFIGURATION ---
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/downloads")
CONFIG_DIR = os.environ.get("CONFIG_DIR", "/config")
APP_DATA_DIR = os.path.join(CONFIG_DIR, "AppData")


st.set_page_config(
    page_title="Cyberdrop-DL GUI",
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
    
    # Quick Disk Usage Check
    total, used, free = shutil.disk_usage(DOWNLOAD_DIR)
    free_gb = free / (2**30)
    st.metric("Free Storage", f"{free_gb:.2f} GB")
    
    st.divider()
    
    ignore_history = st.toggle("Ignore Download History", value=False, help="Re-download files even if they are in the database.")
    force_ipv4 = st.toggle("Force IPv4", value=False, help="Useful if you have IPv6 leaks or VPN issues.")
    
    st.divider()
    st.info(f"📂 Saving to: `{DOWNLOAD_DIR}`")

# --- MAIN LAYOUT ---
st.title("📡 Cyberdrop-DL GUI")
st.markdown("Enter URLs below. [Supported Sites List](https://script-ware.gitbook.io/cyberdrop-dl/reference/supported-websites)")

# URL Input
urls_text = st.text_area("Target URLs (One per line)", height=150, placeholder="https://example.com/thread/123\nhttps://gofile.io/d/ABC")

col1, col2 = st.columns([1, 4])
with col1:
    start_btn = st.button("🚀 Start Download", type="primary", use_container_width=True)
with col2:
    status_text = st.empty()

# --- PROCESSING LOGIC ---
if start_btn and urls_text:
    # 1. Setup Environment
    urls_file = os.path.join(CONFIG_DIR, "urls-current.txt")
    with open(urls_file, "w") as f:
        f.write(urls_text.strip() + "\n")

    # 2. UI Elements for Live Updates
    st.divider()
    
    # Progress Section
    progress_label = st.empty()
    progress_bar = st.progress(0)
    
    # Metrics Row (Live Counters)
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1: metric_dl = st.metric("Downloaded", "0")
    with m_col2: metric_skip = st.metric("Skipped", "0")
    with m_col3: metric_fail = st.metric("Failed", "0")
    with m_col4: metric_found = st.metric("Found", "0")

    # Logs Expander (Hidden by default for cleanness)
    with st.expander("📝 View Raw Terminal Logs", expanded=False):
        log_box = st.empty()

    # 3. Counters
    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "found": 0}
    logs_buffer = []

    # 4. Construct Command
    # We use --ui SIMPLE to get cleaner output for parsing
    cmd = [
        "cyberdrop-dl",
        "-i", urls_file,
        "-d", DOWNLOAD_DIR,
        "--appdata-folder", CONFIG_DIR,
        "--ui", "SIMPLE",             # Simple UI for better parsing
        "--console-log-level", "20",  # INFO level
        "--log-line-width", "500"     # Prevent line wrapping breaking regex
    ]

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
            universal_newlines=True
        )

        progress_label.info("⏳ Initializing scraper...")

        # Regex patterns for parsing
        # Matches: "Downloading: filename.jpg (5.2MB)"
        re_downloading = re.compile(r"Downloading: (.*)")
        # Matches: "Skipped: filename.jpg (Reason)"
        re_skipped = re.compile(r"Skipped:.*")
        # Matches: "Failed: filename.jpg"
        re_failed = re.compile(r"Failed:.*")
        # Matches generic file counters if present
        re_stats = re.compile(r"Downloaded:\s+(\d+).*Skipped.*?(\d+).*Failed.*?(\d+)")

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            
            if line:
                line = line.strip()
                logs_buffer.append(line)
                # Keep log box limited to last 50 lines to prevent lag
                if len(logs_buffer) > 50: logs_buffer.pop(0)
                log_box.code("\n".join(logs_buffer), language="bash")

                # --- LIVE PARSING ---
                
                # Check for downloading status
                if "Downloading:" in line:
                    fname = line.split("Downloading:")[-1].strip()
                    progress_label.info(f"⬇️ Downloading: **{fname}**")
                    status_text.caption("Running...")
                    # Pulse the progress bar
                    progress_bar.progress(int(time.time() * 10) % 100)

                # Check for "Scraping"
                elif "Scraping" in line:
                    progress_label.warning(f"🔍 {line}")

                # Update Counters based on keywords
                if "File Downloaded" in line or "Downloaded:" in line: # Guessing common output based on logs
                    stats["downloaded"] += 1
                    metric_dl.metric("Downloaded", stats["downloaded"])
                
                if "Skipped" in line or "Exists" in line:
                    stats["skipped"] += 1
                    metric_skip.metric("Skipped", stats["skipped"])

                if "Failed" in line or "Error" in line:
                    stats["failed"] += 1
                    metric_fail.metric("Failed", stats["failed"])

                # Try to parse the final block stats if they appear
                # Example: "Download Stats: Downloaded: 82 files Skipped..."
                if "Download Stats:" in line:
                    # We might need to read the next few lines or parse this one
                    pass

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
