# integrated_tts_launcher.py
#!/usr/bin/env python3
"""
Integrated TTS Server + Configuration Manager Launcher
One script to rule them all!
"""

import threading
import time
import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def run_config_manager():
    """Run the simple Flask config manager in a thread"""
    try:
        print("🎛️ Starting Configuration Manager on http://127.0.0.1:5001")
        from simple_config_manager import app
        app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ Error starting Configuration Manager: {e}")
        import traceback
        traceback.print_exc()

def start_tts_server():
    """Start the TTS server"""
    from tts_server import app as tts_app
    try:
        from config.tts_config import SERVER_CONFIG
        host = SERVER_CONFIG.get('host', '0.0.0.0')
        port = SERVER_CONFIG.get('port', 5000)
    except ImportError:
        host = '0.0.0.0'
        port = 5000
    
    print(f"🎤 Starting TTS Server on http://{host}:{port}")
    tts_app.run(host=host, port=port, debug=False, use_reloader=False)

def main():
    print("🚀 Claude-to-Speech Integrated System Starting...")
    print("=" * 50)
    
    # Start config manager in a daemon thread
    config_thread = threading.Thread(target=run_config_manager, daemon=True)
    config_thread.start()
    
    # Give Gradio time to start
    print("Waiting for services to initialize...")
    time.sleep(5)
    
    print("✅ Configuration Manager: http://127.0.0.1:5001")
    print("🎛️ Manage voices, settings, and configurations there")
    print("=" * 50)
    
    # Start TTS server in main thread (this blocks)
    try:
        start_tts_server()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down integrated system...")
        sys.exit(0)

if __name__ == "__main__":
    main()
