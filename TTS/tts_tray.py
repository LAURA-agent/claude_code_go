#!/usr/bin/env python3
"""
System tray icon for TTS Server
Shows custom icon in system tray while server is running
"""

import sys
import threading
import subprocess
from pathlib import Path

try:
    from pystray import Icon, Menu, MenuItem
    from PIL import Image
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    print("Warning: pystray not installed. No system tray icon will be shown.")
    print("Install with: pip3 install pystray pillow")

def run_tts_server():
    """Run the TTS server in a subprocess"""
    script_path = Path(__file__).parent / "tts_launcher.py"
    subprocess.run([sys.executable, str(script_path)])

def create_tray_icon():
    """Create system tray icon for TTS server"""
    if not PYSTRAY_AVAILABLE:
        # Just run the server without tray icon
        run_tts_server()
        return
    
    # Load the icon
    icon_path = "/home/user/rp_client/assets/images/desktop icons/CTS_icon.png"
    try:
        image = Image.open(icon_path)
    except:
        # Create a simple colored square if icon not found
        image = Image.new('RGB', (64, 64), color='blue')
    
    # Create menu
    menu = Menu(
        MenuItem('TTS Server Running', lambda: None, enabled=False),
        MenuItem('Open Config', lambda: subprocess.run(['xdg-open', 'http://localhost:5001'])),
        MenuItem('Quit', lambda icon: icon.stop())
    )
    
    # Create icon
    icon = Icon("TTS Server", image, menu=menu)
    
    # Start server in thread
    server_thread = threading.Thread(target=run_tts_server, daemon=True)
    server_thread.start()
    
    # Run the icon (blocks until quit)
    icon.run()

if __name__ == "__main__":
    create_tray_icon()