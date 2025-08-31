#!/usr/bin/env python3
"""
System tray icon for Text Injection Server
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

def run_injection_server():
    """Run the injection server in a subprocess"""
    script_path = Path(__file__).parent / "apple_watch_server.py"
    subprocess.run([sys.executable, str(script_path)])

def create_tray_icon():
    """Create system tray icon for injection server"""
    if not PYSTRAY_AVAILABLE:
        # Just run the server without tray icon
        run_injection_server()
        return
    
    # Load the icon
    icon_path = "/home/user/rp_client/assets/images/desktop icons/injection.png"
    try:
        image = Image.open(icon_path)
    except:
        # Create a simple colored square if icon not found
        image = Image.new('RGB', (64, 64), color='green')
    
    # Create menu
    menu = Menu(
        MenuItem('Injection Server Running', lambda: None, enabled=False),
        MenuItem('Test Injection', lambda: test_injection()),
        MenuItem('Quit', lambda icon: icon.stop())
    )
    
    # Create icon
    icon = Icon("Text Injection Server", image, menu=menu)
    
    # Start server in thread
    server_thread = threading.Thread(target=run_injection_server, daemon=True)
    server_thread.start()
    
    # Run the icon (blocks until quit)
    icon.run()

def test_injection():
    """Send a test injection request"""
    import requests
    import json
    try:
        response = requests.post(
            'http://localhost:8080/watch/message',
            headers={'Content-Type': 'application/json'},
            data=json.dumps({'text': 'Test injection from tray icon'})
        )
        print(f"Test injection: {response.status_code}")
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    create_tray_icon()