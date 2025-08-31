#!/bin/bash
# Startup script for LAURA Button Controller
# Integrates miniPiTFT hardware buttons with LAURA system

SCRIPT_DIR="/home/user/rp_client/TTS"
CONTROLLER_SCRIPT="advanced_button_controller.py"
PID_FILE="/tmp/button_controller.pid"

# Function to check if controller is already running
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Function to start the controller
start_controller() {
    echo "🎮 Starting LAURA Button Controller..."
    
    cd "$SCRIPT_DIR"
    source ../venv/bin/activate
    
    # Start the controller in background
    python3 "$CONTROLLER_SCRIPT" &
    PID=$!
    
    # Save PID for monitoring
    echo "$PID" > "$PID_FILE"
    
    echo "✅ Button Controller started (PID: $PID)"
    echo "Button functions:"
    echo "  Top (23): Short=LAURA, Long=Volume+"
    echo "  Bottom (24): Short=Claude Voice, Long=Volume-"
}

# Function to stop the controller
stop_controller() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        echo "🛑 Stopping Button Controller (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "✅ Button Controller stopped"
    else
        echo "❌ Button Controller not running"
    fi
}

# Function to restart the controller
restart_controller() {
    stop_controller
    sleep 2
    start_controller
}

# Function to show status
status_controller() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        echo "✅ Button Controller running (PID: $PID)"
    else
        echo "❌ Button Controller not running"
    fi
}

# Main script logic
case "$1" in
    start)
        if is_running; then
            echo "❌ Button Controller already running"
            exit 1
        else
            start_controller
        fi
        ;;
    stop)
        stop_controller
        ;;
    restart)
        restart_controller
        ;;
    status)
        status_controller
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "LAURA Button Controller Management"
        echo "Controls the miniPiTFT hardware buttons"
        exit 1
        ;;
esac