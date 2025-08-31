# GPi Case 2 Button Mapping Guide

## Hardware Details

The GPi Case 2 contains a built-in **Microsoft Xbox 360 Controller** that appears as:
- Device: `/dev/input/event1`
- USB ID: `045e:028e`
- Driver: `xpad` kernel module

## The Zelda-Inspired Mapping Philosophy

We designed the button mapping to feel like playing a Zelda game on a Nintendo console:

| Physical Button | Xbox Code | Keyboard Key | Zelda Logic |
|-----------------|-----------|--------------|-------------|
| **A Button** | BTN_SOUTH (304) | Enter | "Talk/Confirm" - Like talking to NPCs |
| **B Button** | BTN_EAST (305) | Escape | "Cancel/Back" - Exit menus |
| **X Button** | BTN_NORTH (307) | Super/Meta | "Map/Menu" - Pull up overview |
| **Y Button** | BTN_WEST (308) | Backspace | "Item/Delete" - Secondary action |
| **D-Pad** | HAT Axes | Arrow Keys | Movement/Navigation |
| **L Shoulder** | BTN_TL (310) | Left Shift | Modifier key |
| **R Shoulder** | BTN_TR (311) | Tab | Switch between options |
| **Start** | BTN_START (315) | Control+B | Background current task |
| **Select** | BTN_SELECT (314) | / | Navigate slash commands |

## Implementation

The mapping is handled by `/home/user/dpad_to_keyboard.py` which:
1. Reads Xbox controller events from `/dev/input/event1`
2. Grabs exclusive access to prevent double inputs
3. Creates a virtual keyboard via `uinput`
4. Translates button presses to keyboard events

## Key Code Discoveries

Through testing, we found the actual button codes differ from documentation:
- Start button is **315** (not 313 as commonly documented)
- Select button is **314** (not 312 as commonly documented)
- D-pad uses HAT axes, not individual button events

## Service Configuration

The mapper runs as a systemd service:
```bash
# Check status
sudo systemctl status gpi-keyboard-mapper

# Restart if needed
sudo systemctl restart gpi-keyboard-mapper
```

## Customization

To change mappings, edit the button_mapping dictionary in `dpad_to_keyboard.py`:
```python
button_mapping = {
    304: ecodes.KEY_ENTER,      # A button
    305: ecodes.KEY_ESC,         # B button
    307: ecodes.KEY_LEFTMETA,   # X button
    308: ecodes.KEY_BACKSPACE,  # Y button
    # Add your custom mappings here
}
```

## Why This Works So Well

By mapping the controller to keyboard inputs, we get:
- Universal compatibility with all Linux applications
- No need for gamepad support in individual programs
- Consistent navigation across terminal and GUI
- Muscle memory from gaming translates to computing