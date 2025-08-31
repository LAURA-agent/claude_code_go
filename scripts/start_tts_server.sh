#!/bin/bash
# TTS Server Launcher Script
# Starts the TTS server in a terminal window

echo "🎤 Starting TTS Server..."
echo "================================"

# Navigate to TTS directory
cd /home/user/rp_client/TTS

# Activate virtual environment if it exists
if [ -d "/home/user/rp_client/venv" ]; then
    echo "Activating virtual environment..."
    source /home/user/rp_client/venv/bin/activate
fi

# Start the TTS server
echo "Starting TTS server on port 5000..."
python3 tts_launcher.py

# Keep terminal open on exit
echo ""
echo "TTS Server stopped. Press any key to close..."
read -n 1