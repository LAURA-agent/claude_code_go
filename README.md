# GPi Case 2 AI Assistant - Claude Code Game Boy

Take Claude with you on the go in a retro gaming handheld.  An MCP client endpoint in a distributed AI assistant node powered by Claude.

![GPi Case 2](https://img.shields.io/badge/Hardware-GPi%20Case%202-blue)
![Raspberry Pi](https://img.shields.io/badge/Platform-Raspberry%20Pi%20CM4-red)
![Claude](https://img.shields.io/badge/AI-Claude%20Code-purple)
![Python](https://img.shields.io/badge/Python-3.11-green)

## 🎮 Project Overview

This project transforms a GPi Case 2 (Game Boy-style handheld) into a node in a distributed AI assistant network. The device runs Claude Code locally, connects to a larger LAURA network via MCP (Model Context Protocol), and provides voice interaction without built-in microphone hardware.


https://github.com/user-attachments/assets/c6f690f7-d5ea-45f3-80b4-67fb301ea9db


### Key Features

- **Voice Control**: Wake word detection with 6+ trigger phrases (when docked)
- **No Microphone Solution**: Apple Watch integration for voice input via HTTP
- **Pokéball Mouse**: Reverse-engineered Nintendo Pokéball Plus as Bluetooth mouse
- **Game Controller Keyboard**: D-pad and buttons mapped to keyboard inputs
- **Display Management**: Mood-based visual feedback system
- **Distributed AI**: Part of larger LAURA network with sub-agent delegation

## 🛠️ Hardware Requirements

- **GPi Case 2** handheld enclosure
- **Raspberry Pi Compute Module 4** (4GB+ RAM recommended)
- **Pokéball Plus** controller (optional, for mouse control)
- **Apple Watch** or similar device (for voice input)
- **Bluetooth keyboard** (optional)

## 📦 Installation

### Prerequisites

1. **Raspberry Pi OS (64-bit)** - Fresh installation
2. **Python 3.11+** with virtual environment support
3. **Network connection** for MCP server access

### Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/gpi-claude-assistant.git
cd gpi-claude-assistant
```

2. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure API keys:
```bash
cp config/client_secret.example.py config/client_secret.py
cp TTS/config/secret.example.py TTS/config/secret.py
# Edit both files with your API keys
```

5. Fix display configuration:
```bash
# CRITICAL: Edit /boot/firmware/config.txt
# Comment out: #dtoverlay=vc4-kms-v3d
# Add GPi display settings (see docs/display-config.txt)
```

6. Run the system:
```bash
./scripts/master_launcher.sh
```

## 🎯 Core Components

### Voice Input System
- **VOSK**: Local speech-to-text processing
- **Snowboy**: Wake word detection
- **Apple Watch Integration**: HTTP endpoint for remote voice input

### Display System  
- **DPI Interface**: 640x480 display using legacy framebuffer
- **Mood States**: Visual feedback with Claude/LAURA personas
- **Pygame**: Display management and image rendering

### Input Mapping
- **Game Controller**: Xbox 360 controller mapped to keyboard
- **Pokéball Plus**: Bluetooth LE mouse control
- **Keyboard Shortcuts**: Push-to-talk and command triggers

### AI Integration
- **MCP Client**: Connects to distributed LAURA network
- **Claude Code**: Programming-focused sub-agent
- **TTS**: ElevenLabs API for voice output

## 🗂️ Project Structure

```
rp_client/
├── TTS/                    # Text-to-speech system
├── claude/                 # Claude Code integration
├── speech_capture/         # VOSK speech recognition
├── snowboy/               # Wake word models
├── system/                # Core system management
├── display/               # Visual display manager
├── scripts/               # Launch and utility scripts
└── assets/                # Images and sounds
```

## 🚀 Usage

### Voice Commands
- Say "Hey LAURA" for general assistant
- Say "Claude Code" for programming tasks
- Use Apple Watch Shortcuts app for voice input

### Button Controls
| Button | Keyboard | Function |
|--------|----------|----------|
| A | Enter | Confirm |
| B | Escape | Cancel |
| X | Super/Meta | Menu |
| Y | Backspace | Delete |
| D-Pad | Arrow Keys | Navigate |
| L | Shift | Modifier |
| R | Tab | Tab navigation |

### Pokéball Mouse
1. Reset Pokéball with pin
2. Press top button for pairing
3. Run pairing script:
```bash
sudo bluetoothctl
scan on
# Find "Pokemon PBP"
pair [MAC_ADDRESS]
```

## 📝 Configuration

### MCP Server Connection
Edit `client_settings.json`:
```json
{
  "SERVER_URL": "http://your-mcp-server:8765",
  "DEVICE_ID": "your-device-name"
}
```

### Voice Configuration
Modify wake words in `snowboy/` directory or adjust sensitivity in settings.

### Display Settings
Critical boot configuration in `/boot/firmware/config.txt` - see documentation for DPI settings.

## 🔧 Troubleshooting

### Black Screen
- Ensure `vc4-kms-v3d` is commented out in boot config
- Check DPI24 overlay is enabled
- Verify display timings match GPi Case 2 specs

### No Audio
- Check TTS server is running: `curl http://localhost:5000/status`
- Verify ElevenLabs API key is configured
- Test with: `python3 TTS/speak.py "Test message"`

### Button Input Issues
- Verify mapper service: `sudo systemctl status gpi-keyboard-mapper`
- Check Xbox controller detection: `ls /dev/input/event*`
- Test with: `sudo evtest /dev/input/event1`

## 🤝 Contributing

Contributions welcome! This project showcases human-AI collaboration with 100% Claude-written code.

### Development Setup
1. Fork the repository
2. Create feature branch
3. Follow existing code patterns
4. Test on actual GPi Case 2 hardware
5. Submit pull request

## 📚 Documentation

- [Display Configuration Guide](docs/display-config.md)
- [Button Mapping Details](docs/button-mapping.md)
- [Pokéball Reverse Engineering](docs/pokeball-protocol.md)
- [Network Architecture](docs/network-architecture.md)

## 🏆 Acknowledgments

- **Claude (Anthropic)**: All code written by Claude
- **Hardware**: Retroflag GPi Case 2
- **Inspiration**: Steven Universe (Ruby squad distributed consciousness)
- **Reverse Engineering**: 8-hour Pokéball Plus protocol breakthrough

## 📄 License

MIT License - See LICENSE file for details

## ⚠️ Disclaimer

This project involves hardware modifications and reverse engineering. Proceed at your own risk. Not affiliated with Nintendo, Retroflag, or Anthropic.

---

*Built with ❤️ by Carson and Claude*

*Submitted to Anthropic Discord - August 2025*
