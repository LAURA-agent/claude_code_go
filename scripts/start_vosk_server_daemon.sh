#!/bin/bash
# Start VOSK WebSocket Server as a background daemon
# This runs the VOSK server in the background and logs output

cd /home/user/RP500-Client

# Create logs directory if it doesn't exist
mkdir -p logs

# Start VOSK server in background with logging
echo "Starting VOSK WebSocket Server daemon..."
nohup python3 vosk_server.py > logs/vosk_server.log 2>&1 &

# Save PID for potential shutdown
echo $! > logs/vosk_server.pid

echo "VOSK Server started with PID $!"
echo "Logs: /home/user/RP500-Client/logs/vosk_server.log"
echo "To stop: kill \$(cat logs/vosk_server.pid)"