#!/usr/bin/env python3

import asyncio
import time
import random
import select
from datetime import datetime
from pathlib import Path
from typing import Optional
from evdev import InputDevice, list_devices, ecodes
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
from colorama import Fore


class InputManager:
    """
    Manages all input detection including keyboard and wake word monitoring.
    
    Handles wake event detection, keyboard monitoring, and coordination
    between different input sources.
    """
    
    def __init__(self, audio_manager):
        self.audio_manager = audio_manager
        self.keyboard_device = None
        self.last_interaction = time.time()
        self.last_interaction_check = time.time()
        
        # Key state tracking for modifier detection
        self.keys_pressed = set()
        
        # Cooldown for keyboard events to prevent double triggers
        self.keyboard_cooldown_until = 0
        
        # Initialize GPIO buttons
        self.gpio_initialized = False
        self.button_press_start = {}
        self.button_hold_time = 2.0  # seconds for long press
        if GPIO_AVAILABLE:
            self._init_gpio_buttons()
            
        # Button click tracking for annoyance system
        self.button_click_counts = {23: 0, 24: 0}
        self.last_button_pressed = None
        self.current_persona = "laura"  # "laura" or "claude_code"
        
        # Wake word detection attributes
        self.wake_detector = None
        self.wake_model_names = None
        self.wake_pa = None
        self.wake_stream = None
        self.wake_last_break = None
        
    def find_pi_keyboard(self):
        """Find keyboard device with proper priority and logging"""
        if not InputDevice: 
            print(f"{Fore.YELLOW}[WARN] evdev not available, keyboard detection disabled{Fore.WHITE}")
            return None
            
        print(f"\n{Fore.CYAN}=== Keyboard Initialization ==={Fore.WHITE}")
        print(f"{Fore.CYAN}Available input devices:{Fore.WHITE}")
        
        keyboard_devices = []
        for path in list_devices():
            try:
                device = InputDevice(path)
                print(f"  - {device.path}: {device.name}")
                
                # Check if we can read from this device
                try:
                    select.select([device.fd], [], [], 0)
                    
                    # Check for keyboard devices (Pi 500, K780, etc.)
                    is_keyboard = False
                    priority = 0
                    
                    # Pi 500 keyboard (original priority)
                    if "Pi 500" in device.name and "Keyboard" in device.name:
                        is_keyboard = True
                        if "event5" in device.path:
                            priority = 100  # Prioritize event5 as it receives KEY_LEFTMETA
                        elif "event10" in device.path:
                            priority = 90   # event10 is secondary
                        else:
                            priority = 50
                    
                    # Logitech K780 keyboard (high priority)
                    elif "K780" in device.name and "Keyboard" in device.name:
                        is_keyboard = True
                        priority = 95  # High priority for K780
                    
                    # Generic keyboard detection (lower priority)
                    elif ("Keyboard" in device.name and 
                          "Mouse" not in device.name and 
                          "Consumer" not in device.name and 
                          "System" not in device.name and
                          "AVRCP" not in device.name):
                        is_keyboard = True
                        priority = 30
                            
                    if is_keyboard and priority > 0:
                        try:
                            device.grab()
                            device.ungrab()
                            keyboard_devices.append((device, priority))
                            print(f"    {Fore.GREEN}✓ Keyboard found: {device.name} (priority: {priority}){Fore.WHITE}")
                        except Exception as e:
                            print(f"    {Fore.YELLOW}✗ Cannot grab device: {e}{Fore.WHITE}")
                            device.close()
                    else:
                        device.close()
                        
                except Exception as e:
                    print(f"    {Fore.YELLOW}✗ Cannot read device: {e}{Fore.WHITE}")
                    device.close()
                    
            except Exception as e:
                print(f"    {Fore.RED}Error with device {path}: {e}{Fore.WHITE}")

        if keyboard_devices:
            keyboard_devices.sort(key=lambda x: x[1], reverse=True)
            keyboard_device = keyboard_devices[0][0]
            print(f"{Fore.GREEN}✓ Using keyboard device: {keyboard_device.path} ({keyboard_device.name}){Fore.WHITE}")
            print(f"{Fore.GREEN}✓ Using keyboard without exclusive access to allow normal typing{Fore.WHITE}")
            return keyboard_device
        else:
            print(f"{Fore.YELLOW}✗ No valid Keyboard found{Fore.WHITE}")
            return None

    def initialize_keyboard(self):
        """Initialize keyboard input detection"""
        self.keyboard_device = self.find_pi_keyboard()
        return self.keyboard_device is not None
    
    def _refresh_keyboard_device(self):
        """Refresh keyboard device when connection is lost"""
        try:
            # Close old device if it exists
            if self.keyboard_device:
                try:
                    self.keyboard_device.close()
                except:
                    pass
                self.keyboard_device = None
            
            # Clear pressed keys state
            self.keys_pressed.clear()
            
            # Try to find keyboard again
            self.keyboard_device = self.find_pi_keyboard()
            
            if self.keyboard_device:
                print("[INFO] Keyboard device refreshed successfully")
            else:
                print("[WARN] Failed to refresh keyboard device")
                
        except Exception as e:
            print(f"[ERROR] Error refreshing keyboard device: {e}")
            self.keyboard_device = None

    def _listen_keyboard_sync(self) -> str | None:
        """Synchronous keyboard check for wake event"""
        if not self.keyboard_device or not ecodes:
            return None
        
        # Check if we're in cooldown period
        if time.time() < self.keyboard_cooldown_until:
            return None
            
        try:
            # Check if keyboard device is still valid
            if self.keyboard_device.fd < 0:
                print("[WARN] Keyboard device has invalid file descriptor, refreshing...")
                self._refresh_keyboard_device()
                return None
                
            ready, _, _ = select.select([self.keyboard_device.fd], [], [], 0.001)
            if ready:
                for event in self.keyboard_device.read():
                    if event.type == ecodes.EV_KEY:
                        # Track key state changes
                        if event.value == 1:  # Key press
                            self.keys_pressed.add(event.code)
                        elif event.value == 0:  # Key release
                            self.keys_pressed.discard(event.code)
                        
                        # Check for left meta press
                        if (event.code == ecodes.KEY_LEFTMETA and event.value == 1):
                            # Check if shift is currently held
                            if ecodes.KEY_LEFTSHIFT in self.keys_pressed:
                                print("[INFO] SHIFT+Left Meta detected - routing to Claude Code")
                                return "keyboard_code"
                            else:
                                print("[INFO] Left Meta detected - routing to LAURA")
                                return "keyboard_laura"
                                
        except (BlockingIOError, OSError, ValueError) as e:
            if "file descriptor" in str(e):
                print(f"[WARN] Keyboard device error: {e}")
                self._refresh_keyboard_device()
            pass
            
        return None

    async def wake_word_detection(self):
        """Wake word detection with notification-aware breaks"""
        import pyaudio
        import sys
        import os
        # Add snowboy directory to Python path
        snowboy_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'snowboy')
        if snowboy_path not in sys.path:
            sys.path.insert(0, snowboy_path)
        import snowboydetect
        from config.client_config import WAKE_WORDS_AND_SENSITIVITIES as WAKE_WORDS, WAKEWORD_RESOURCE_FILE, WAKEWORD_MODEL_DIR
        
        # One-time initialization
        if not self.wake_detector:
            try:
                print(f"{Fore.YELLOW}Initializing wake word detector...{Fore.WHITE}")

                # Explicitly define resource path
                resource_path = Path(WAKEWORD_RESOURCE_FILE)

                # Set the directory where all wake word models are kept
                wakeword_dir = Path(WAKEWORD_MODEL_DIR)

                # Build model paths from filenames in WAKE_WORDS
                model_paths = [wakeword_dir / name for name in WAKE_WORDS.keys()]

                # Check for missing files
                missing = [str(path.absolute()) for path in [resource_path] + model_paths if not path.exists()]
                if missing:
                    print(f"ERROR: The following required file(s) are missing:\n" + "\n".join(missing))
                    return None

                # Build sensitivities list, ensuring order matches models
                sensitivities = []
                for p in model_paths:
                    sensitivity = WAKE_WORDS.get(p.name)
                    if sensitivity is None:
                        print(f"WARNING: No sensitivity found for {p.name}. Defaulting to 0.5.")
                        sensitivity = 0.5
                    sensitivities.append(str(sensitivity))
                if len(sensitivities) != len(model_paths):
                    print("ERROR: Sensitivities count does not match model paths count!")
                    return None

                # Initialize the detector
                self.wake_detector = snowboydetect.SnowboyDetect(
                    resource_filename=str(resource_path.absolute()).encode(),
                    model_str=",".join(str(p.absolute()) for p in model_paths).encode()
                )
                sensitivity_bytes = ",".join(sensitivities).encode()
                self.wake_detector.SetSensitivity(sensitivity_bytes)
                self.wake_model_names = [p.name for p in model_paths]
                self.wake_pa = pyaudio.PyAudio()
                self.wake_stream = None
                self.wake_last_break = time.time()
                print(f"{Fore.GREEN}Wake word detector initialized with models: {self.wake_model_names}{Fore.WHITE}")
            except Exception as e:
                print(f"Error initializing wake word detection: {e}")
                return None

        try:
            # Create/restart stream if needed
            if not self.wake_stream or not self.wake_stream.is_active():
                self.wake_stream = self.wake_pa.open(
                    rate=16000,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=1024
                )
                self.wake_stream.start_stream()

            # Periodic breaks for notifications and keyboard recheck (every 30 seconds)
            current_time = time.time()
            if (current_time - self.wake_last_break) >= 30:
                self.wake_last_break = current_time
                if self.wake_stream:
                    self.wake_stream.stop_stream()
                    
                    # During break: check for keyboard reconnection if needed
                    if not self.keyboard_device:
                        print("[INFO] Checking for keyboard reconnection during TTS break...")
                        self._refresh_keyboard_device()
                    
                    await asyncio.sleep(0.6)  # 0.6-second break
                    self.wake_stream.start_stream()
                return None

            # Read audio with error handling
            try:
                data = self.wake_stream.read(1024, exception_on_overflow=False)
                if len(data) == 0:
                    print("Warning: Empty audio frame received")
                    return None
            except (IOError, OSError) as e:
                print(f"Stream read error: {e}")
                if self.wake_stream:
                    self.wake_stream.stop_stream()
                    self.wake_stream.close()
                    self.wake_stream = None
                return None

            result = self.wake_detector.RunDetection(data)
            if result > 0:
                print(f"{Fore.GREEN}Wake word detected! (Model {result}){Fore.WHITE}")
                # Don't update last_interaction here - only update on successful user interactions
                return self.wake_model_names[result-1] if result <= len(self.wake_model_names) else None

            # Occasionally yield to event loop (much less frequently)
            if random.random() < 0.01:
                await asyncio.sleep(0)

            return None

        except Exception as e:
            print(f"Error in wake word detection: {e}")
            if self.wake_stream:
                self.wake_stream.stop_stream()
                self.wake_stream.close()
                self.wake_stream = None
            return None

    def stop_wake_word_detection(self):
        """Stop wake word detection and release microphone for voice input"""
        try:
            if self.wake_stream:
                print("[DEBUG] Stopping wake word stream to release microphone")
                self.wake_stream.stop_stream()
                self.wake_stream.close()
                self.wake_stream = None
        except Exception as e:
            print(f"[DEBUG] Error stopping wake stream: {e}")
    
    def restart_wake_word_detection(self):
        """Restart wake word detection after voice input is complete"""
        try:
            if not self.wake_stream and self.wake_pa and self.wake_detector:
                print("[DEBUG] Restarting wake word detection")
                import pyaudio  # Import pyaudio locally
                self.wake_stream = self.wake_pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=1024
                )
        except Exception as e:
            print(f"[DEBUG] Error restarting wake stream: {e}")

    async def check_for_wake_events(self):
        """Check for wake events from keyboard, buttons, or wake word"""
        wake_event_source = None
        
        # Check keyboard first
        keyboard_event = self._listen_keyboard_sync()
        if keyboard_event:
            wake_event_source = keyboard_event  # Can be "keyboard_laura" or "keyboard_code"
            print(f"[INFO] Wake event from keyboard: {keyboard_event}")
        else:
            # Check GPIO buttons (now only handles voice cycling, no wake events)
            self._check_gpio_buttons()
            
            # Check wake word
            wakeword_model = await self.wake_word_detection()
            if wakeword_model:
                wake_event_source = f"wakeword ({wakeword_model})"
                print(f"[INFO] Wake event from: {wake_event_source}")
        
        return wake_event_source

    def update_last_interaction(self):
        """Update last interaction timestamp - call this only on successful user interactions"""
        self.last_interaction = time.time()
        print(f"[DEBUG] Last interaction updated to {self.last_interaction}")
    
    def set_keyboard_cooldown(self, duration=1.5):
        """Set a cooldown period for keyboard events (prevents double triggers)"""
        self.keyboard_cooldown_until = time.time() + duration
        print(f"[INFO] Keyboard cooldown set for {duration} seconds")

    def get_time_since_last_interaction(self):
        """Get seconds since last interaction"""
        return time.time() - self.last_interaction

    def cleanup(self):
        """Clean up keyboard and GPIO resources"""
        if self.keyboard_device:
            self.keyboard_device.close()
            self.keyboard_device = None
        if GPIO_AVAILABLE and self.gpio_initialized:
            GPIO.cleanup()

    def _init_gpio_buttons(self):
        """Initialize GPIO buttons for miniPiTFT"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Top button
            GPIO.setup(24, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Bottom button
            self.gpio_initialized = True
            print("[INFO] GPIO buttons initialized (pins 23, 24)")
        except Exception as e:
            print(f"[WARN] Failed to initialize GPIO buttons: {e}")
            self.gpio_initialized = False

    def _check_gpio_buttons(self):
        """Check GPIO buttons and return wake event if pressed"""
        if not GPIO_AVAILABLE or not self.gpio_initialized:
            return None
            
        current_time = time.time()
        
        try:
            # Check button 23 (top) - for LAURA
            if GPIO.input(23) == 0:  # Button pressed (active low)
                if 23 not in self.button_press_start:
                    self.button_press_start[23] = current_time
                    print("[DEBUG] Button 23 (top) pressed - starting timer")
                return None  # Wait for release
            elif 23 in self.button_press_start:
                # Button released
                press_duration = current_time - self.button_press_start[23]
                del self.button_press_start[23]
                if press_duration < self.button_hold_time:
                    print(f"[INFO] Button 23 short press ({press_duration:.2f}s) - LAURA persona confirmation")
                    self._handle_persona_button_press(23)
                    return None
                else:
                    print(f"[INFO] Button 23 long press ({press_duration:.2f}s) - Run LAURA MCP tool")
                    self._run_laura_mcp_tool()
                    return None
            
            # Check button 24 (bottom) - for Claude Code  
            if GPIO.input(24) == 0:  # Button pressed (active low)
                if 24 not in self.button_press_start:
                    self.button_press_start[24] = current_time
                    print("[DEBUG] Button 24 (bottom) pressed - starting timer")
                return None  # Wait for release
            elif 24 in self.button_press_start:
                # Button released
                press_duration = current_time - self.button_press_start[24]
                del self.button_press_start[24]
                if press_duration < self.button_hold_time:
                    print(f"[INFO] Button 24 short press ({press_duration:.2f}s) - Claude Code persona confirmation")
                    self._handle_persona_button_press(24)
                    return None
                else:
                    print(f"[INFO] Button 24 long press ({press_duration:.2f}s) - Claude Code voice injection")
                    self._launch_claude_code_voice_injection()
                    return None
                    
        except Exception as e:
            print(f"[WARN] GPIO button check error: {e}")
            
        return None

    def _handle_volume_up(self):
        """Handle volume up button action"""
        try:
            import subprocess
            subprocess.run(['amixer', 'set', 'Master', '5%+'], capture_output=True)
            print("✅ Volume increased")
        except Exception as e:
            print(f"❌ Volume up error: {e}")

    def _handle_volume_down(self):
        """Handle volume down button action"""
        try:
            import subprocess
            subprocess.run(['amixer', 'set', 'Master', '5%-'], capture_output=True)
            print("✅ Volume decreased")
        except Exception as e:
            print(f"❌ Volume down error: {e}")

    def reset_button_counters(self):
        """Reset button click counters (called when user sends message or switches persona)"""
        self.button_click_counts = {23: 0, 24: 0}
        print("[DEBUG] Button click counters reset")

    def _handle_persona_button_press(self, button_number):
        """Handle persona confirmation button press with annoyance tracking"""
        try:
            # Determine target persona based on button
            if button_number == 23:
                target_persona = "laura"
                voice_id = "qEwI395unGwWV1dn3Y65"  # Laura voice ID
            elif button_number == 24:
                target_persona = "claude_code" 
                voice_id = "uY96J30mUhYUIymmD5cu"  # Claude Code voice ID
            else:
                return
            
            # Check if switching personas (resets counter)
            if self.last_button_pressed != button_number:
                print(f"[INFO] Switching to {target_persona} persona")
                self.current_persona = target_persona
                self.reset_button_counters()
                self.last_button_pressed = button_number
                
                # Update active voice in voices.json
                self._update_active_voice(voice_id)
            
            # Increment click counter for this button
            self.button_click_counts[button_number] += 1
            click_count = self.button_click_counts[button_number]
            
            print(f"[INFO] Button {button_number} pressed {click_count} times ({target_persona})")
            
            # Play appropriate annoyance level audio
            self._play_annoyance_audio(button_number, click_count)
            
        except Exception as e:
            print(f"[ERROR] Error handling persona button press: {e}")

    def _update_active_voice(self, voice_id):
        """Update active voice in voices.json"""
        try:
            import json
            voices_file = "/home/user/rp_client/TTS/config/voices.json"
            
            with open(voices_file, 'r') as f:
                voices_data = json.load(f)
            
            voices_data['active_voice'] = voice_id
            
            with open(voices_file, 'w') as f:
                json.dump(voices_data, f, indent=2)
                
            print(f"[INFO] Updated active voice to: {voice_id}")
            
        except Exception as e:
            print(f"[ERROR] Failed to update active voice: {e}")

    def _play_annoyance_audio(self, button_number, click_count):
        """Play audio based on annoyance level from click count"""
        try:
            import subprocess
            import os
            import random
            
            # Determine annoyance level folder
            if click_count <= 3:
                level_folder = "1-3"
            elif click_count <= 5:
                level_folder = "4-5"
            elif click_count <= 7:
                level_folder = "6-7"
            elif click_count <= 9:
                level_folder = "8-9"
            else:  # 10+
                level_folder = "10"
            
            # Look for audio files in the annoyance level folder
            audio_dir = f"/home/user/rp_client/assets/sounds/button_audio/button{button_number}/{level_folder}"
            
            if os.path.exists(audio_dir):
                # Get all mp3 files in the folder
                audio_files = [f for f in os.listdir(audio_dir) if f.endswith('.mp3')]
                
                if audio_files:
                    # Pick random file from the folder
                    chosen_file = random.choice(audio_files)
                    audio_path = os.path.join(audio_dir, chosen_file)
                    
                    subprocess.Popen(['mpg123', '-q', audio_path])
                    print(f"[INFO] Playing annoyance level {level_folder}: {chosen_file}")
                    return
            
            # Fallback to default if no annoyance audio found
            fallback_path = f"/home/user/rp_client/assets/sounds/button_audio/button{button_number}/default.mp3"
            if os.path.exists(fallback_path):
                subprocess.Popen(['mpg123', '-q', fallback_path])
                print(f"[INFO] Playing fallback audio (no annoyance level found)")
            else:
                print(f"[WARN] No audio found for button {button_number}, level {level_folder}")
                
        except Exception as e:
            print(f"[ERROR] Failed to play annoyance audio: {e}")

    def _run_laura_mcp_tool(self):
        """Execute run_LAURA MCP tool"""
        try:
            import subprocess
            
            print("[INFO] Launching run_LAURA MCP tool...")
            
            # Run the LAURA script in background
            subprocess.Popen([
                'python3', 
                '/home/user/rp_client/run.py'
            ], cwd='/home/user/rp_client')
            
            print("✅ run_LAURA MCP tool launched successfully")
            
            # Optional: Play confirmation sound
            try:
                subprocess.Popen(['mpg123', '-q', '/home/user/rp_client/assets/sounds/sound_effects/cc_confirm.mp3'])
            except:
                pass
                
        except Exception as e:
            print(f"❌ Failed to launch run_LAURA MCP tool: {e}")

    def _launch_claude_code_voice_injection(self):
        """Launch Claude Code voice injection system"""
        try:
            import subprocess
            
            print("[INFO] Launching Claude Code voice injection...")
            
            # Launch the voice injection script
            subprocess.Popen([
                'python3',
                '/home/user/rp_client/claude/simple_voice_injector.py'
            ], cwd='/home/user/rp_client')
            
            print("✅ Claude Code voice injection launched successfully")
            
            # Optional: Play confirmation sound
            try:
                subprocess.Popen(['mpg123', '-q', '/home/user/rp_client/assets/sounds/sound_effects/teletype.mp3'])
            except:
                pass
                
        except Exception as e:
            print(f"❌ Failed to launch Claude Code voice injection: {e}")