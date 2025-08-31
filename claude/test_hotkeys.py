#!/usr/bin/env python3
"""
Quick hotkey tester for finding good Claude Code voice input combinations
"""

import evdev
from evdev import ecodes
import sys
import time

def find_keyboard():
    """Find the Logitech K780 keyboard"""
    for device_path in evdev.list_devices():
        device = evdev.InputDevice(device_path)
        if 'k780' in device.name.lower() or ('keyboard' in device.name.lower() and 'logitech' in device.name.lower()):
            return evdev.InputDevice(device_path)
    return None

def main():
    keyboard = find_keyboard()
    if not keyboard:
        print("❌ Could not find Logitech K780 keyboard")
        sys.exit(1)
        
    print(f"✅ Found keyboard: {keyboard.name}")
    print("\n🎯 Test these key combinations (press them to see if they register):")
    print("   Ctrl+Shift+Space  (good option)")
    print("   Ctrl+Alt+V        (voice)")  
    print("   Alt+Shift+C       (claude)")
    print("   Ctrl+Shift+M      (microphone)")
    print("   Shift+Space       (simple)")
    print("\n   Press Ctrl+C to exit\n")
    
    # Track modifier states
    ctrl_pressed = False
    shift_pressed = False
    alt_pressed = False
    
    try:
        for event in keyboard.read_loop():
            if event.type == ecodes.EV_KEY and event.value == 1:  # Key press only
                
                # Update modifier states
                if event.code in [ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL]:
                    ctrl_pressed = True
                elif event.code in [ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT]:
                    shift_pressed = True
                elif event.code in [ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT]:
                    alt_pressed = True
                elif event.code == ecodes.KEY_SPACE:
                    modifiers = []
                    if ctrl_pressed: modifiers.append("Ctrl")
                    if shift_pressed: modifiers.append("Shift") 
                    if alt_pressed: modifiers.append("Alt")
                    
                    if modifiers:
                        combo = "+".join(modifiers) + "+Space"
                        print(f"🎹 Detected: {combo}")
                        
                elif event.code == ecodes.KEY_V:
                    modifiers = []
                    if ctrl_pressed: modifiers.append("Ctrl")
                    if shift_pressed: modifiers.append("Shift")
                    if alt_pressed: modifiers.append("Alt")
                    
                    if modifiers:
                        combo = "+".join(modifiers) + "+V"
                        print(f"🎹 Detected: {combo}")
                        
                elif event.code == ecodes.KEY_C:
                    modifiers = []
                    if ctrl_pressed: modifiers.append("Ctrl")
                    if shift_pressed: modifiers.append("Shift")
                    if alt_pressed: modifiers.append("Alt")
                    
                    if modifiers:
                        combo = "+".join(modifiers) + "+C"
                        print(f"🎹 Detected: {combo}")
                        
                elif event.code == ecodes.KEY_M:
                    modifiers = []
                    if ctrl_pressed: modifiers.append("Ctrl")
                    if shift_pressed: modifiers.append("Shift")
                    if alt_pressed: modifiers.append("Alt")
                    
                    if modifiers:
                        combo = "+".join(modifiers) + "+M"
                        print(f"🎹 Detected: {combo}")
                        
            elif event.type == ecodes.EV_KEY and event.value == 0:  # Key release
                # Reset modifier states
                if event.code in [ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL]:
                    ctrl_pressed = False
                elif event.code in [ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT]:
                    shift_pressed = False
                elif event.code in [ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT]:
                    alt_pressed = False
                    
    except KeyboardInterrupt:
        print("\n👋 Testing completed!")

if __name__ == "__main__":
    main()