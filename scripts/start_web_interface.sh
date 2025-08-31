#!/bin/bash

# Start the Flask web interface for LAURA Control Center

cd /home/user/rp_client
source venv/bin/activate
cd web_interface
echo "Starting LAURA Control Center web interface..."
echo "Access at: http://localhost:7860"
python app.py