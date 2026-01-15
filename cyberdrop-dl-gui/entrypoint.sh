#!/bin/bash
set -e
set -x  # <--- Prints every command to docker logs

echo "--- ENTRYPOINT STARTING ---"
echo "Current User: $(id)"
echo "Checking /config permissions..."
ls -ld /config || echo "/config does not exist yet"

# Ensure config dir exists
mkdir -p /config/cyberdrop
echo "Created/Verified /config/cyberdrop"

# Set env for cyberdrop-dl config path
export XDG_CONFIG_HOME=/config

echo "--- STARTING STREAMLIT ---"
# We do NOT use 'exec' here so we can trap errors if streamlit fails immediately
streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
