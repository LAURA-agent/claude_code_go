#!/usr/bin/env python3
"""
D-pad to Keyboard Mapper for GPi Case 2
Custom mapping for text navigation and editing
"""

import evdev
from evdev import InputDevice, UInput, ecodes
import sys
import time

def find_xbox_controller():
    """Find the Xbox 360 controller device"""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        if "X-Box 360 pad" in device.name or "Xbox" in device.name:
            return device
    return None

def create_keyboard_mapper():
    """Create virtual keyboard for key injection"""
    return UInput({
        ecodes.EV_KEY: [
            ecodes.KEY_UP,
            ecodes.KEY_DOWN,
            ecodes.KEY_LEFT,
            ecodes.KEY_RIGHT,
            ecodes.KEY_ENTER,       # A button
            ecodes.KEY_ESC,         # B button
            ecodes.KEY_DELETE,      # X button
            ecodes.KEY_BACKSPACE,   # Y button
            ecodes.KEY_LEFTSHIFT,   # L shoulder
            ecodes.KEY_TAB,         # R shoulder
            ecodes.KEY_LEFTMETA,    # X button (Super/Windows key)
            ecodes.KEY_SLASH,       # Select button (changed to slash)
            ecodes.KEY_HOME,        # Home/Xbox button
            ecodes.KEY_LEFTCTRL,    # For Ctrl+B combo
            ecodes.KEY_B,           # For Ctrl+B combo
        ]
    })

def main():
    print("🎮 GPi Case 2 Controller → Keyboard Mapper")
    print("=" * 50)
    
    # Find controller
    controller = find_xbox_controller()
    if not controller:
        print("❌ No Xbox 360 controller found!")
        sys.exit(1)
    
    print(f"✅ Found: {controller.name}")
    print("📍 Custom button mappings active:")
    print()
    print("Button Mappings:")
    print("  D-pad     → Arrow Keys")
    print("  A         → Enter")
    print("  B         → Escape")
    print("  X         → Super/Meta")
    print("  Y         → Backspace")
    print("  L Trigger → Shift")
    print("  R Trigger → Tab")
    print("  Start     → B")
    print("  Select    → Ctrl")
    print("  RetroFlag → / (tap) or Delete (hold)")
    print("  Star/Turbo→ / (if not in turbo mode)")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    # Grab exclusive access to prevent double input
    try:
        controller.grab()
        print("✅ Exclusive access - no double inputs")
    except:
        print("⚠️  Could not grab exclusive access - may see double inputs")
    
    # Create virtual keyboard
    ui = create_keyboard_mapper()
    
    # Track D-pad state to handle releases
    dpad_x_pressed = False
    dpad_y_pressed = False
    
    # Track flag button timing for dual function
    flag_press_time = None
    
    try:
        for event in controller.read_loop():
            # D-pad HAT axes to arrow keys
            if event.type == ecodes.EV_ABS:
                if event.code == 16:  # HAT0X (left/right)
                    if event.value == -1:  # Left
                        ui.write(ecodes.EV_KEY, ecodes.KEY_LEFT, 1)  # Press
                        dpad_x_pressed = True
                    elif event.value == 1:  # Right
                        ui.write(ecodes.EV_KEY, ecodes.KEY_RIGHT, 1)  # Press
                        dpad_x_pressed = True
                    elif event.value == 0 and dpad_x_pressed:  # Released
                        # Release both left and right
                        ui.write(ecodes.EV_KEY, ecodes.KEY_LEFT, 0)
                        ui.write(ecodes.EV_KEY, ecodes.KEY_RIGHT, 0)
                        dpad_x_pressed = False
                        
                elif event.code == 17:  # HAT0Y (up/down)
                    if event.value == -1:  # Up
                        ui.write(ecodes.EV_KEY, ecodes.KEY_UP, 1)  # Press
                        dpad_y_pressed = True
                    elif event.value == 1:  # Down
                        ui.write(ecodes.EV_KEY, ecodes.KEY_DOWN, 1)  # Press
                        dpad_y_pressed = True
                    elif event.value == 0 and dpad_y_pressed:  # Released
                        # Release both up and down
                        ui.write(ecodes.EV_KEY, ecodes.KEY_UP, 0)
                        ui.write(ecodes.EV_KEY, ecodes.KEY_DOWN, 0)
                        dpad_y_pressed = False
            
            # Button mappings (using your exact specifications)
            elif event.type == ecodes.EV_KEY:
                if event.code == 304:  # A button → Enter
                    ui.write(ecodes.EV_KEY, ecodes.KEY_ENTER, event.value)
                elif event.code == 305:  # B button → Escape
                    ui.write(ecodes.EV_KEY, ecodes.KEY_ESC, event.value)
                elif event.code == 307:  # X button → Super/Meta (changed from Delete)
                    ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTMETA, event.value)
                elif event.code == 308:  # Y button → Backspace
                    ui.write(ecodes.EV_KEY, ecodes.KEY_BACKSPACE, event.value)
                elif event.code == 310:  # L shoulder → Shift
                    ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTSHIFT, event.value)
                elif event.code == 311:  # R shoulder → Tab
                    ui.write(ecodes.EV_KEY, ecodes.KEY_TAB, event.value)
                elif event.code == 315:  # Start button → B
                    ui.write(ecodes.EV_KEY, ecodes.KEY_B, event.value)
                elif event.code == 314:  # Select button → Ctrl
                    ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, event.value)
                elif event.code == 316:  # RetroFlag button (flag icon) → Slash (tap) or Delete (hold)
                    if event.value == 1:  # Button pressed
                        flag_press_time = time.time()
                    elif event.value == 0 and flag_press_time:  # Button released
                        hold_duration = time.time() - flag_press_time
                        if hold_duration < 0.3:  # Quick tap (less than 300ms)
                            # Send slash
                            ui.write(ecodes.EV_KEY, ecodes.KEY_SLASH, 1)
                            ui.write(ecodes.EV_KEY, ecodes.KEY_SLASH, 0)
                            print("/ (flag tap)")
                        else:  # Hold (300ms or more)
                            # Send delete
                            ui.write(ecodes.EV_KEY, ecodes.KEY_DELETE, 1)
                            ui.write(ecodes.EV_KEY, ecodes.KEY_DELETE, 0)
                            print("DEL (flag hold)")
                        flag_press_time = None
                elif event.code == 317:  # Star/Turbo button → Slash
                    ui.write(ecodes.EV_KEY, ecodes.KEY_SLASH, event.value)
                elif event.code == 318:  # Unknown button → Available
                    pass  # Available for future functionality
                
            # Sync events
            ui.syn()
                    
    except KeyboardInterrupt:
        print("\n✋ Mapper stopped")
    finally:
        controller.ungrab()
        ui.close()

if __name__ == "__main__":
    main()