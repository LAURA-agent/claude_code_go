#!/usr/bin/env python3
"""
Claude Code Voice Input Manager
Lightweight clipboard-based voice input for Pi hardware
"""

import asyncio
import subprocess
import os
import time
import threading
import select
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime
try:
    from evdev import InputDevice, categorize, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False
    print("[WARNING] evdev not available - keyboard hotkeys disabled")

from system.audio_manager import AudioManager
from speech_capture.vosk_websocket_adapter import VoskTranscriber
from config.client_config import VOSK_MODEL_PATH, AUDIO_SAMPLE_RATE
from claude.claude_tts_notifier import ClaudeTTSNotifier


class VoiceInputManager:
    """Manages voice input capture and clipboard integration with multi-input support"""
    
    def __init__(self):
        self.audio_manager = AudioManager(sample_rate=AUDIO_SAMPLE_RATE)
        self.transcriber = VoskTranscriber(model_path=VOSK_MODEL_PATH, sample_rate=AUDIO_SAMPLE_RATE)
        self.tts = ClaudeTTSNotifier('/home/user/rp_client/tts_notifications')
        self.is_capturing = False
        self.hotkey_active = False
        self.keyboard_device = None
        
        # Input method setup
        self.clipboard_cmd = self._detect_clipboard_tool()
        if not self.clipboard_cmd:
            print("[WARNING] No clipboard tool found. Install xclip or wl-clipboard")
            
        # Initialize keyboard monitoring for Logitech K780
        self._setup_keyboard_monitoring()
        
    def _setup_keyboard_monitoring(self):
        """Setup keyboard monitoring for hotkey detection"""
        if not EVDEV_AVAILABLE:
            return
            
        try:
            # Find Logitech K780 or any keyboard device
            import evdev
            devices = [InputDevice(path) for path in evdev.list_devices()]
            
            for device in devices:
                if 'keyboard' in device.name.lower() or 'k780' in device.name.lower():
                    self.keyboard_device = device
                    print(f"[INFO] Found keyboard: {device.name}")
                    break
                    
            if not self.keyboard_device:
                # Fallback to any keyboard-like device
                for device in devices:
                    caps = device.capabilities()
                    if ecodes.EV_KEY in caps:
                        self.keyboard_device = device
                        print(f"[INFO] Using keyboard device: {device.name}")
                        break
                        
        except Exception as e:
            print(f"[WARNING] Keyboard setup failed: {e}")
            
    def start_hotkey_monitoring(self, callback: Callable):
        """Start monitoring for keyboard hotkeys (Ctrl+Start for Claude Code voice)"""
        if not self.keyboard_device or self.hotkey_active:
            return
            
        self.hotkey_active = True
        
        def monitor_hotkeys():
            print("[INFO] Hotkey monitoring started (Ctrl+Start for voice input)")
            
            try:
                ctrl_pressed = False
                
                for event in self.keyboard_device.read_loop():
                    if not self.hotkey_active:
                        break
                        
                    if event.type == ecodes.EV_KEY:
                        # Track Ctrl key state
                        if event.code in [ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL]:
                            ctrl_pressed = event.value == 1
                            
                        # Check for Start/Super key press with Ctrl
                        elif event.code in [ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA] and event.value == 1:
                            if ctrl_pressed:
                                print("\n🎤 Hotkey triggered: Ctrl+Start")
                                asyncio.run_coroutine_threadsafe(callback(), asyncio.get_event_loop())
                                
            except Exception as e:
                print(f"[ERROR] Hotkey monitoring error: {e}")
                
        # Start in background thread
        threading.Thread(target=monitor_hotkeys, daemon=True).start()
        
    def stop_hotkey_monitoring(self):
        """Stop hotkey monitoring"""
        self.hotkey_active = False
        
    def _detect_clipboard_tool(self) -> Optional[str]:
        """Detect available clipboard tool (xclip or wl-copy)"""
        # Check for xclip (X11)
        try:
            subprocess.run(['which', 'xclip'], capture_output=True, check=True)
            return 'xclip'
        except:
            pass
            
        # Check for wl-copy (Wayland)
        try:
            subprocess.run(['which', 'wl-copy'], capture_output=True, check=True)
            return 'wl-copy'
        except:
            pass
            
        return None
        
    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to system clipboard"""
        if not self.clipboard_cmd:
            print("[ERROR] No clipboard tool available")
            return False
            
        try:
            if self.clipboard_cmd == 'xclip':
                # Use xclip for X11
                process = subprocess.Popen(['xclip', '-selection', 'clipboard'], 
                                         stdin=subprocess.PIPE)
                process.communicate(text.encode('utf-8'))
            else:
                # Use wl-copy for Wayland
                process = subprocess.Popen(['wl-copy'], stdin=subprocess.PIPE)
                process.communicate(text.encode('utf-8'))
                
            return process.returncode == 0
            
        except Exception as e:
            print(f"[ERROR] Failed to copy to clipboard: {e}")
            return False
            
    def save_transcription_log(self, text: str):
        """Save transcription to log file for history"""
        log_dir = Path("/home/user/rp_client/logs/voice_input")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"voice_input_{timestamp}.txt"
        
        try:
            with open(log_file, 'w') as f:
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Transcription:\n{text}\n")
            print(f"[INFO] Saved to: {log_file}")
        except Exception as e:
            print(f"[ERROR] Failed to save log: {e}")
            
    async def play_sound(self, sound_name: str):
        """Play a sound effect"""
        sound_file = f"/home/user/rp_client/assets/sounds/sound_effects/{sound_name}.mp3"
        if os.path.exists(sound_file):
            try:
                subprocess.run(['mpg123', '-q', sound_file], capture_output=True)
            except:
                pass  # Fail silently if mpg123 not available
                
    async def play_ready_sound(self):
        """Play sound when transcription is ready"""
        await self.play_sound("successfulloadup")
        
    async def play_start_sound(self):
        """Play radar ping sound when capture starts"""
        await self.play_sound("radarping")
        
    async def play_typing_sound(self):
        """Play teletype sound during transcription"""
        await self.play_sound("teletype")
                
    async def capture_voice_for_clipboard(self, duration: int = 60) -> Optional[str]:
        """
        Capture voice input and copy to clipboard
        
        Args:
            duration: Maximum capture duration in seconds
            
        Returns:
            Transcribed text if successful
        """
        if self.is_capturing:
            print("[WARNING] Already capturing")
            return None
            
        self.is_capturing = True
        print(f"\n🎤 Voice capture started (max {duration}s)")
        print("   Speak now... Press Meta key again to stop early")
        
        # Play radar ping sound
        await self.play_start_sound()
        
        # Send TTS notification
        self.tts.update_status("Voice capture started. Speak now.")
        
        try:
            # Initialize audio
            await self.audio_manager.initialize_input()
            audio_stream = await self.audio_manager.start_listening()
            
            if not audio_stream:
                print("[ERROR] Failed to start audio stream")
                return None
                
            # Reset transcriber for new session
            self.transcriber.reset()
            
            start_time = time.time()
            frames_processed = 0
            last_update = 0
            last_typing_sound = 0
            speech_detected = False
            
            while time.time() - start_time < duration:
                # Read audio frame
                pcm_bytes = self.audio_manager.read_audio_frame()
                if not pcm_bytes:
                    await asyncio.sleep(0.005)
                    continue
                    
                # Process frame
                is_final, is_speech, current_text = self.transcriber.process_frame(pcm_bytes)
                frames_processed += 1
                
                # Play typing sound when speech is being processed
                current_time = time.time()
                if is_speech and current_text and len(current_text.strip()) > 0:
                    if not speech_detected:
                        speech_detected = True
                        # Play typing sound when first speech is detected
                        await self.play_typing_sound()
                        last_typing_sound = current_time
                    elif current_time - last_typing_sound > 3.0:  # Every 3 seconds during active speech
                        await self.play_typing_sound()
                        last_typing_sound = current_time
                
                # Show progress every second
                if current_time - last_update > 1.0:
                    elapsed = int(current_time - start_time)
                    if current_text:
                        print(f"\r[{elapsed}s] Words: {len(current_text.split())} | "
                              f"Last: ...{current_text[-30:]}", end='', flush=True)
                    else:
                        print(f"\r[{elapsed}s] Listening...", end='', flush=True)
                    last_update = current_time
                    
                # Check for manual stop (would need keyboard integration)
                # For now, just continue until timeout
                
            print("\n")  # New line after progress
            
            # Get final transcription
            final_text = self.transcriber.get_final_text()
            
            if final_text and final_text.strip():
                print(f"\n📝 Transcribed: {final_text}")
                
                # Copy to clipboard
                if self.copy_to_clipboard(final_text):
                    print("✅ Copied to clipboard! Press Ctrl+Shift+V to paste in Claude Code")
                    self.tts.update_status("Transcription ready in clipboard. Press Control Shift V to paste.")
                    await self.play_ready_sound()
                else:
                    print("❌ Failed to copy to clipboard")
                    self.tts.warn_user("Failed to copy to clipboard")
                    
                # Save to log
                self.save_transcription_log(final_text)
                
                return final_text
            else:
                print("❌ No speech detected")
                self.tts.update_status("No speech detected")
                return None
                
        except Exception as e:
            print(f"[ERROR] Voice capture failed: {e}")
            self.tts.report_error(f"Voice capture error: {str(e)}")
            return None
            
        finally:
            self.is_capturing = False
            await self.audio_manager.stop_listening()
            print("\n🛑 Voice capture ended")


async def test_voice_input():
    """Test the voice input system"""
    print("🎤 Claude Code Voice Input Test")
    print("================================")
    
    manager = VoiceInputManager()
    
    if not manager.clipboard_cmd:
        print("\n⚠️  No clipboard tool found!")
        print("Install one of these:")
        print("  - sudo apt-get install xclip  (for X11)")
        print("  - sudo apt-get install wl-clipboard  (for Wayland)")
        return
        
    print(f"\n✅ Using clipboard tool: {manager.clipboard_cmd}")
    print("\nPress Enter to start voice capture (or Ctrl+C to quit)")
    
    try:
        input()
        result = await manager.capture_voice_for_clipboard(duration=30)
        
        if result:
            print(f"\n✅ Success! Text is in your clipboard")
            print("📋 You can now paste it into Claude Code with Ctrl+Shift+V")
        else:
            print("\n❌ No transcription captured")
            
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    asyncio.run(test_voice_input())