#!/usr/bin/env python3
"""
Send Enter Key Script
Uses evdev/uinput to send a single Enter key press
"""

import time
from evdev import UInput, ecodes as e

def send_enter():
    """Send a single Enter key press using virtual keyboard"""
    capabilities = {
        e.EV_KEY: [e.KEY_ENTER]
    }
    
    try:
        with UInput(capabilities, name='claude-enter-sender', version=0x3) as ui:
            print("[ENTER] Virtual keyboard created, sending Enter...")
            time.sleep(0.2)  # Brief delay for device recognition
            
            # Send Enter key press
            ui.write(e.EV_KEY, e.KEY_ENTER, 1)  # Key down
            ui.write(e.EV_KEY, e.KEY_ENTER, 0)  # Key up
            ui.syn()
            
            print("[ENTER] ✓ Enter key sent successfully!")
            
    except Exception as ex:
        print(f"[ENTER] ✗ Failed to send Enter: {ex}")
        return False
    
    return True

if __name__ == "__main__":
    success = send_enter()
    exit(0 if success else 1)