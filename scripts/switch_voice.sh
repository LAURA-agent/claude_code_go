#!/bin/bash
#
# Switch TTS Voice and Restart Server
# Usage: ./switch_voice.sh [laura|claude]
#

VOICE="$1"
CONFIG_FILE="/home/user/rp_client/TTS/config/voices.json"

# Voice IDs
LAURA_ID="qEwI395unGwWV1dn3Y65"
CLAUDE_ID="uY96J30mUhYUIymmD5cu"

if [ -z "$VOICE" ]; then
    echo "Usage: ./switch_voice.sh [laura|claude]"
    echo "Current voice: $(grep active_voice $CONFIG_FILE | cut -d'"' -f4)"
    exit 1
fi

echo "🔄 Switching TTS voice to: $VOICE"

# Update the config file based on choice
case "$VOICE" in
    laura|Laura|LAURA)
        sed -i "s/\"active_voice\": \".*\"/\"active_voice\": \"$LAURA_ID\"/" "$CONFIG_FILE"
        echo "✅ Voice set to Laura"
        ;;
    claude|Claude|CLAUDE)
        sed -i "s/\"active_voice\": \".*\"/\"active_voice\": \"$CLAUDE_ID\"/" "$CONFIG_FILE"
        echo "✅ Voice set to Claude"
        ;;
    *)
        echo "❌ Invalid voice. Choose 'laura' or 'claude'"
        exit 1
        ;;
esac

# Kill existing TTS server
echo "🛑 Stopping TTS server..."
pkill -f "tts_launcher.py" 2>/dev/null
pkill -f "tts_server.py" 2>/dev/null
sleep 2

# Restart TTS server in background
echo "🚀 Starting TTS server with new voice..."
cd /home/user/rp_client/TTS
source /home/user/rp_client/venv/bin/activate
nohup python3 tts_launcher.py > /tmp/tts_server.log 2>&1 &
NEW_PID=$!

sleep 3

# Check if server started successfully
if kill -0 $NEW_PID 2>/dev/null; then
    echo "✅ TTS server restarted with $VOICE voice (PID: $NEW_PID)"
    
    # Test the new voice
    echo "🔊 Testing new voice..."
    if [ "$VOICE" == "claude" ] || [ "$VOICE" == "Claude" ] || [ "$VOICE" == "CLAUDE" ]; then
        python3 /home/user/rp_client/TTS/speak.py "Hello! This is Claude speaking with a British accent."
    else
        python3 /home/user/rp_client/TTS/speak.py "Hi! This is Laura speaking with a bubbly voice."
    fi
else
    echo "❌ Failed to start TTS server. Check /tmp/tts_server.log for errors"
    exit 1
fi