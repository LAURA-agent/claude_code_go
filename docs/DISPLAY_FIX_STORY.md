# The GPi Case 2 Display Fix Story

## The Problem

When setting up the GPi Case 2 with standard Raspberry Pi OS, users encounter a black screen after boot. The display works during initial boot (rainbow screen visible) but goes black when the OS loads.

## The Investigation

We spent days debugging this issue, trying:
- Different HDMI settings
- Various display overlays
- Multiple resolution configurations
- Different OS versions

## The Breakthrough

The critical discovery: The modern `vc4-kms-v3d` driver is completely incompatible with the GPi Case 2's DPI display interface.

## The Solution

**Comment out or delete this line in `/boot/firmware/config.txt`:**
```
#dtoverlay=vc4-kms-v3d
```

This forces the system to use the legacy `bcm2708_fb` framebuffer driver instead.

## Why This Works

### Modern KMS Driver (vc4-kms-v3d) - DOESN'T WORK
- Expects EDID display identification
- Negotiates display modes dynamically
- Supports hot-plugging
- Uses DRM/KMS architecture
- The GPi LCD has none of these capabilities

### Legacy Framebuffer (bcm2708_fb) - WORKS PERFECTLY
- Direct pixel pushing to hardware
- No display negotiation
- Fixed resolution configuration
- Simple memory-mapped framebuffer
- Perfect for fixed-hardware displays like GPi

## Technical Details

The GPi Case 2 uses a **DPI24** (24-bit Display Parallel Interface) that requires:
- 24 parallel RGB data lines
- Pixel clock signal
- Horizontal/vertical sync signals
- Exact timing parameters

The display controller expects raw RGB data at exact timings. Any attempt to negotiate or detect display capabilities fails because this is essentially "dumb" hardware that just displays whatever pixels you send at the configured timing.

## The Complete Configuration

```bash
# Disable modern driver (CRITICAL!)
#dtoverlay=vc4-kms-v3d

# Enable DPI interface
dtoverlay=dpi24
framebuffer_width=640
framebuffer_height=480
enable_dpi_lcd=1
display_default_lcd=1

# Custom timing for GPi LCD
dpi_group=2
dpi_mode=87
dpi_output_format=0x00016  # RGB888 format (8 bits per color channel)
hdmi_timings=640 0 41 40 41 480 0 18 9 18 0 0 0 60 0 24000000 1

# Disable HDMI to prevent conflicts
hdmi_blanking=2
hdmi_ignore_hotplug=1
```

### About dpi_output_format

The `dpi_output_format=0x00016` setting is crucial. This hexadecimal value specifies:
- **RGB888 format**: 8 bits for red, 8 bits for green, 8 bits for blue
- **24-bit color depth**: Full color range
- **Correct byte ordering** for the GPi display controller

Without this setting, colors may appear wrong or the display might not sync properly.

## Verification

After applying these settings and rebooting:
```bash
# Check display state - CRITICAL VERIFICATION
tvservice -s
# Should show: state 0x400000 [LCD], 640x480
# The 0x400000 specifically means LCD mode is active!

# Check framebuffer
fbset
# Should show: 
# mode "640x480"
# geometry 640 480 640 480 32
# Using /dev/fb0

# Check driver
lsmod | grep fb
# Should show: bcm2708_fb (NOT vc4)

# Verify framebuffer device
cat /proc/fb
# Should show: 0 BCM2708 FB
```

## Critical Warnings

**NEVER use these commands with GPi Case 2:**
```bash
# DO NOT USE - Will freeze/crash the system!
tvservice -p  # Preferred mode - FREEZES SYSTEM
tvservice -o  # Turn off display - FREEZES SYSTEM
fbset [any resolution change]  # Causes black screen
```

These commands are HDMI-only and will cause the DPI display to lock up!

## Common Mistakes

1. **Leaving vc4-kms-v3d enabled** - This will always result in black screen
2. **Wrong timing values** - Must use exact values shown above
3. **Trying to use HDMI** - GPi uses DPI, not HDMI
4. **Wrong overlay** - Must be `dpi24`, not `dpi18` or others

## Impact

This single configuration fix is the difference between:
- ❌ Black screen, unusable device
- ✅ Perfect 640x480 display, fully functional Game Boy

Without this discovery, the entire project would have been impossible.