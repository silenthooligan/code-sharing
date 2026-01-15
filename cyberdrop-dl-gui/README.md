# 📡 Cyberdrop-DL GUI

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg) ![License](https://img.shields.io/badge/license-MIT-green.svg) ![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)

> **The Visual Downloader**. A modern, web-based graphical interface for the powerful [`cyberdrop-dl`](https://github.com/jbsparrow/CyberDropDownloader) tool.

---

## 🚀 Why This Tool?

The original [`cyberdrop-dl`](https://github.com/jbsparrow/CyberDropDownloader) is an incredible command-line utility, but not everyone loves the terminal. **Cyberdrop-DL GUI** wraps the core engine in a beautiful, responsive Streamlit interface that makes downloading albums as easy as pasting a link.

### ✨ Features

*   **🖥️ Web Interface**: Clean, dark-mode UI powered by Streamlit.
*   **📊 real-time Progress**: Visual progress bars and live status updates for every file.
*   **📈 Live Statistics**: Track downloaded, skipped, and failed files in real-time.
*   **🐳 Docker Ready**: Pre-packaged container with all dependencies and `aria2` optimized configuration.
*   **📋 Batch Processing**: Paste multiple URLs at once and let it run.

---

## 🛠️ Installation

### Option 1: Docker (Recommended)

The easiest way to run the tool is via Docker.

1.  **Clone the Repo**:
    ```bash
    git clone https://github.com/silenthooligan/code-sharing.git
    cd code-sharing/cyberdrop-dl-gui
    ```

2.  **Build the Image**:
    ```bash
    docker build -t cyberdrop-dl-gui .
    ```

2.  **Run the Container**:
    ```bash
    docker run -d -p 8501:8501 \
      -v $(pwd)/downloads:/downloads \
      -v $(pwd)/config:/config \
      cyberdrop-dl-gui
    ```

3.  **Access the UI**:
    Open your browser and navigate to `http://localhost:8501`.

### Configuration

The application uses the following Environment Variables to determine where to save files.

| Variable | Description | Docker Default | Local Default |
| :--- | :--- | :--- | :--- |
| `DOWNLOAD_DIR` | Where files are saved. | `/downloads` | `/downloads` |
| `CONFIG_DIR` | Where temporary configs live. | `/config` | `/config` |

> **Note**: For local Python usage, you should export these variables to point to a writable directory, e.g.:
> `export DOWNLOAD_DIR=./my_downloads`

### Option 2: Local Python

1.  **Clone the Repo**:
    ```bash
    git clone https://github.com/silenthooligan/code-sharing.git
    cd code-sharing/cyberdrop-dl-gui
    ```

2.  **Install Dependencies**:
    Requires `aria2` to be installed on your system (e.g., `sudo apt install aria2` or `brew install aria2`).
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the App**:
    ```bash
    export DOWNLOAD_DIR=./downloads
    export CONFIG_DIR=./config
    mkdir -p downloads config
    streamlit run app.py
    ```

---

## 📖 Usage

1.  **Paste URLs**: Enter one or more supported URLs.
    *   [View Full List of Supported Sites](https://script-ware.gitbook.io/cyberdrop-dl/reference/supported-websites)
2.  **Configure Settings**: Toggle "Ignore History" if you want to force re-downloads.
3.  **Start Download**: Click the **🚀 Start Download** button.
4.  **Monitor**: Watch the logs and progress bars as your files are acquired.

---

## 🤝 Credits & Acknowledgements

Standing on the shoulders of giants.

*   **Original Tool**: [`cyberdrop-dl`](https://github.com/jbsparrow/CyberDropDownloader) by **Jules-WinnfieldX** (maintained by **jbsparrow**). The core logic that makes this possible.
*   **Patched Version**: maintained by the community to keep up with site changes (`cyberdrop-dl-patched`).
*   **GUI Wrapper**: Created for the open-source community.

---

**Happy Archiving!** 💾
