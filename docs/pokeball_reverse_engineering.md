# The 8-Hour Pokéball Plus Reverse Engineering Story

## The Challenge

The GPi Case 2 has no external USB ports and no built-in mouse. We needed a wireless pointing device. While searching for a PS4 controller, I found a Pokéball Plus from my son's Pokemon Let's Go game (2018) and thought: "Why not?"

## The Problem

The Pokéball Plus was notoriously difficult to decode. The X-axis data seemed encrypted or encoded in a way that made no sense. Other reverse engineers had tried and failed to fully decode the protocol.

## The Journey

### Hour 1-3: Initial Attempts
- Connected via Bluetooth Low Energy
- Could read Y-axis (analog, smooth)
- X-axis data was gibberish
- Found Reddit posts and GitHub repos with similar struggles

### Hour 4-6: Data Collection
- Built multiple debuggers
- Captured thousands of data packets
- Tried various decoding algorithms
- Hit dead end after dead end

### Hour 7: The Collaboration
- Took all collected data to Gemini for fresh perspective
- Gemini suggested creating a visual dashboard
- Brought idea back to Claude Code
- Claude built an improved real-time byte visualization tool

### Hour 8: The Breakthrough

After just 5 minutes watching the dashboard while moving the joystick, I noticed a pattern in the low nibble of byte[3]:

```
LEFT:   0010, 0011 (binary: 001X)
CENTER: 0111      (binary: 01XX)  
RIGHT:  1100+     (binary: 1XXX)
```

**The last bit was noise!** This simple observation solved what others had tried complex calculations to decode.

## The Solution

```python
def decode_x_axis(byte3):
    low_nibble = byte3 & 0x0F
    low_nibble = low_nibble >> 1  # Ignore last bit
    
    if low_nibble == 0b001:  # Left
        return -1
    elif low_nibble == 0b011:  # Center
        return 0
    elif low_nibble >= 0b100:  # Right
        return 1
```

## BLE Packet Structure

| Byte | Content | Type |
|------|---------|------|
| 0 | Packet counter | Counter |
| 1 | Button state | 00=none, 01=B, 02=A |
| 3 | X-axis (low nibble) | Digital (bit pattern) |
| 4 | Y-axis | Analog (32-192 range) |

## Technical Details

- **MAC Address**: Device-specific (format: XX:XX:XX:XX:XX:XX)
- **Service UUID**: Device-specific
- **Characteristic**: `6675e16c-f36d-4567-bb55-6b51e27a23e6`
- **Connection**: Bluetooth Low Energy (BLE)

## The Result

A fully functional Pokéball Plus mouse driver that:
- Provides smooth analog Y-axis movement
- Digital left/center/right X-axis control
- Top button for left click
- Stick press for right click
- Auto-calibration on startup

## Lessons Learned

1. **Multi-AI Collaboration Works**: Claude provided tools, Gemini offered fresh perspective
2. **Visual Debugging is Powerful**: The dashboard made the pattern obvious
3. **Simple Solutions Hide in Complex Data**: The answer was just ignoring one bit
4. **Human Pattern Recognition**: Sometimes human eyes catch what algorithms miss

## Why This Matters

This Pokéball mouse solution:
- Solves the "no USB ports" problem elegantly
- Adds perfect thematic consistency (Nintendo peripheral for Game Boy device)
- Demonstrates the power of persistence and collaboration
- Shows that "impossible" reverse engineering is often just one insight away

The 8-hour investment turned a toy Pokéball into a functional computer mouse, completing the Game Boy transformation.