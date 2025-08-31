# GPi Case 2 Display Configuration Guide

## Critical Boot Configuration

The GPi Case 2 uses a DPI (Display Parallel Interface) that requires specific settings in `/boot/firmware/config.txt`.

### Required Changes

1. **DISABLE Modern KMS Driver** (Most Important!)
```bash
# MUST BE COMMENTED OUT:
#dtoverlay=vc4-kms-v3d
```

2. **Enable DPI Display Settings**
```bash
# GPi Case 2 Display Configuration
dtoverlay=dpi24
framebuffer_width=640
framebuffer_height=480
enable_dpi_lcd=1
display_default_lcd=1
dpi_group=2
dpi_mode=87
dpi_output_format=0x00016
hdmi_timings=640 0 41 40 41 480 0 18 9 18 0 0 0 60 0 24000000 1

# Disable HDMI completely
hdmi_blanking=2
hdmi_ignore_hotplug=1
display_auto_detect=0
```

### Why This Works

- **Legacy Framebuffer**: Uses bcm2708_fb driver instead of modern KMS
- **Fixed Resolution**: 640x480 is the native resolution
- **DPI24**: 24-bit parallel RGB interface
- **No HDMI Switching**: Prevents dock detection issues

### Troubleshooting

**Black Screen After Boot**
- Verify `vc4-kms-v3d` is commented out
- Check all DPI settings are exactly as shown
- Reboot after changes

**Display Flickering**
- Ensure power supply is adequate (3A+ recommended)
- Check ribbon cable connection

**Wrong Resolution**
- Framebuffer must be exactly 640x480
- Do not change hdmi_timings values