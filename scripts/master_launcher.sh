#!/bin/bash
#
# Master Launcher Script with Service Detection
# Checks if services are already running before starting them
# 
# Services:
# 1. Pokeball mouse control (background)
# 2. TTS Server (background)
# 3. Text Injection Server (background)
# 4. LAURA main client (foreground)
#

echo "🚀 Starting LAURA System Components..."
echo "======================================"

# Function to check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
    return $?
}

# Function to check if a port is in use
port_in_use() {
    netstat -tuln 2>/dev/null | grep -q ":$1 "
    return $?
}

# Track PIDs of services we start
POKEBALL_PID=""
TTS_PID=""
INJECTION_PID=""

# 1. Start Pokeball mouse control in background
echo "🎮 Checking Pokeball mouse control..."
if is_running "pokeball_mouse_working.py"; then
    echo "   ⚠️  Pokeball already running, skipping..."
else
    echo "   Starting Pokeball mouse control..."
    nohup python3 /home/user/pokeball/pokeball_mouse_working.py > /tmp/pokeball.log 2>&1 &
    POKEBALL_PID=$!
    echo "   ✓ Pokeball started (PID: $POKEBALL_PID)"
    sleep 2
fi

# 2. Start TTS Server in background
echo "🔊 Checking TTS Server..."
if port_in_use 5000; then
    echo "   ⚠️  TTS Server already running on port 5000, skipping..."
else
    echo "   Starting TTS Server..."
    cd /home/user/rp_client/TTS
    source /home/user/rp_client/venv/bin/activate
    nohup python3 tts_launcher.py > /tmp/tts_server.log 2>&1 &
    TTS_PID=$!
    echo "   ✓ TTS Server started (PID: $TTS_PID)"
    sleep 3
fi

# 3. Start Text Injection Server in background
echo "💉 Checking Text Injection Server..."
if is_running "apple_watch_server.py"; then
    echo "   ⚠️  Injection Server already running, skipping..."
else
    echo "   Starting Text Injection Server..."
    cd "/home/user/rp_client/voice injection/scripts"
    source /home/user/rp_client/venv/bin/activate
    nohup python3 apple_watch_server.py > /tmp/injection_server.log 2>&1 &
    INJECTION_PID=$!
    echo "   ✓ Injection Server started (PID: $INJECTION_PID)"
    sleep 2
fi

# 4. Check if LAURA is already running
echo "🤖 Checking LAURA..."
if is_running "run.py"; then
    echo "   ⚠️  LAURA is already running!"
    echo "   Would you like to kill the existing instance and restart? (y/n)"
    read -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "   Stopping existing LAURA instance..."
        pkill -f "run.py"
        sleep 2
    else
        echo "   Exiting without starting new LAURA instance."
        exit 0
    fi
fi

# Start LAURA in foreground (so terminal stays open)
echo "🤖 Starting LAURA..."
echo "======================================"
cd /home/user/rp_client
source venv/bin/activate

# Create a cleanup function - only kill services we started
cleanup() {
    echo ""
    echo "Shutting down services we started..."
    [ ! -z "$POKEBALL_PID" ] && kill $POKEBALL_PID 2>/dev/null && echo "   Stopped Pokeball"
    [ ! -z "$TTS_PID" ] && kill $TTS_PID 2>/dev/null && echo "   Stopped TTS Server"
    [ ! -z "$INJECTION_PID" ] && kill $INJECTION_PID 2>/dev/null && echo "   Stopped Injection Server"
    echo "Cleanup complete."
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Run LAURA (this blocks until user exits)
python3 run.py

# When LAURA exits, the trap will clean up only the background services we started