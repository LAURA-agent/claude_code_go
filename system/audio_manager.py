#!/usr/bin/env python3

import os
import time
import asyncio
import pyaudio
from mutagen.mp3 import MP3
from asyncio import Event
import numpy as np
from dataclasses import dataclass
from typing import Optional, Dict, Any
import traceback
os.environ['PULSE_SERVER'] = 'unix:/run/user/1000/pulse/native'

@dataclass
class AudioManagerState:
    """
    Centralized state tracking for audio system.
    
    Attributes:
        is_playing (bool): Indicates if any audio is currently playing
        is_speaking (bool): Indicates if TTS audio is currently playing
        is_listening (bool): Indicates if audio input is being captured
        playback_start_time (float): Timestamp when current audio started
        current_audio_file (str): Path to currently playing audio file
        expected_duration (float): Expected duration of current audio in seconds
    """
    is_playing: bool = False
    is_speaking: bool = False
    is_listening: bool = False
    playback_start_time: Optional[float] = None
    current_audio_file: Optional[str] = None
    expected_duration: Optional[float] = None

class AudioManager:
    """
    Manages audio input/output operations with proper state tracking and resource management.
    
    This class handles:
    - Audio input capture for speech recognition
    - Audio playback for TTS and notification sounds
    - State tracking for coordination with other system components
    """
    
    def __init__(self, sample_rate: int = 16000):
        """
        Initialize AudioManager with required resources and state tracking.
        
        Args:
            sample_rate (int): The sample rate to use for audio operations.
        """
        import ctypes
        import datetime
        
        os.makedirs('logs', exist_ok=True)
        log_file = f"logs/audio_init_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int,
                                             ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)
        def py_error_handler(filename, line, function, err, fmt):
            with open(log_file, 'a') as f:
                f.write(f'ALSA: {function} {fmt}\n')
        
        c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
        try:
            asound = ctypes.CDLL('libasound.so.2')
            asound.snd_lib_error_set_handler(c_error_handler)
        except:
            pass
        
        self.pa = pyaudio.PyAudio()
        self.audio_stream = None
        self.current_process = None
        
        self.audio_complete = Event()
        self.audio_complete.set()
        
        self.activation_lock = asyncio.Lock()
        self.playback_lock = asyncio.Lock()
        self.state_lock = asyncio.Lock()
        
        self.state = AudioManagerState()
        
        self.sample_rate = sample_rate
        self.frame_length = 2048
        
        print(f"\n=== Audio System Initialization ===")
        print(f"Sample Rate: {self.sample_rate} Hz")
        print(f"Frame Length: {self.frame_length} samples")
        print("=================================\n")

    async def get_state(self) -> Dict[str, Any]:
        """Get current audio system state in a thread-safe manner."""
        async with self.state_lock:
            return self.state.__dict__

    @property
    def is_playing(self):
        return self.state.is_playing
        
    @property
    def is_speaking(self):
        return self.state.is_speaking
    
    @property
    def is_listening(self):
        return self.state.is_listening
    
    @property
    def playback_start_time(self):
        return self.state.playback_start_time
    
    @property
    def current_audio_file(self):
        return self.state.current_audio_file
    
    @property
    def expected_duration(self):
        return self.state.expected_duration
                
    async def initialize_input(self):
        """Initialize audio input stream for capturing speech."""
        async with self.activation_lock:
            if self.audio_stream is None:
                try:
                    # Force using pulse device instead of default to match higher energy levels
                    # Default device seems to have noise reduction/processing that reduces energy
                    pulse_device_index = None
                    for i in range(self.pa.get_device_count()):
                        device_info = self.pa.get_device_info_by_index(i)
                        if device_info['name'] == 'pulse' and device_info['maxInputChannels'] > 0:
                            pulse_device_index = i
                            break
                    
                    if pulse_device_index is not None:
                        print(f"[AUDIO DEBUG] Using pulse device (index {pulse_device_index}) for raw audio")
                        device_index = pulse_device_index
                    else:
                        default_input = self.pa.get_default_input_device_info()
                        print(f"[AUDIO DEBUG] Fallback to default device: {default_input['name']} (index {default_input['index']})")
                        device_index = default_input['index']
                    
                    self.audio_stream = self.pa.open(
                        input_device_index=device_index,
                        rate=self.sample_rate,
                        channels=1,
                        format=pyaudio.paInt16,
                        input=True,
                        frames_per_buffer=self.frame_length
                    )
                except Exception as e:
                    print(f"[ERROR] Failed to open PyAudio stream: {e}")
                    traceback.print_exc()
                    raise

    async def start_listening(self):
        """Start audio input capture for speech recognition."""
        if self.state.is_speaking:
            await self.audio_complete.wait()
        
        # Note: initialize_input() should be called before this method
        async with self.state_lock:
            self.state.is_listening = True
        return self.audio_stream, None

    async def stop_listening(self):
        """Stop audio input capture and cleanup resources."""
        async with self.state_lock:
            self.state.is_listening = False
        
        if self.audio_stream:
            try:
                if self.audio_stream.is_active():
                    self.audio_stream.stop_stream()
                if not self.audio_stream.is_stopped():
                    self.audio_stream.close()
            except Exception as e:
                print(f"[ERROR] Failed to close audio stream: {e}")
            finally:
                self.audio_stream = None
        
        print("[AUDIO MANAGER] Audio input stream stopped and reset.")

    async def play_audio(self, audio_file: str):
        """
        Play audio file using mpg123 with full state tracking.
        """
        async with self.playback_lock:
            async with self.state_lock:
                self.state.is_speaking = True
                self.state.is_playing = True
                self.state.playback_start_time = time.time()
                self.state.current_audio_file = audio_file
            self.audio_complete.clear()
            
            try:
                try:
                    audio = MP3(audio_file)
                    async with self.state_lock:
                        self.state.expected_duration = audio.info.length
                except Exception as e:
                    async with self.state_lock:
                        self.state.expected_duration = 2.0
                
                # USE MPG123 FOR STABLE PLAYBACK WITH AUTOMATIC OUTPUT DETECTION
                command = f'/usr/bin/mpg123 -q "{audio_file}"'
                print(f"[AudioManager] Executing playback: {command}")
                
                self.current_process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                
                # Wait for actual audio duration instead of process completion
                audio_duration = self.state.expected_duration
                wait_duration = audio_duration  # No buffer - audio ends when it ends
                max_wait = min(wait_duration, 60.0)   # Cap at 60 seconds for safety
                
                print(f"[AudioManager] Waiting {wait_duration:.1f}s for audio duration ({audio_duration:.1f}s)")
                
                # Start background task to manage process timeout
                async def manage_process():
                    try:
                        process_timeout = max(audio_duration + 5.0, 15.0)  # Generous process timeout
                        await asyncio.wait_for(self.current_process.wait(), timeout=process_timeout)
                    except asyncio.TimeoutError:
                        print(f"[AudioManager] Process timeout after {process_timeout:.1f}s, terminating mpg123")
                        self.current_process.terminate()
                        try:
                            await asyncio.wait_for(self.current_process.wait(), timeout=2.0)
                        except asyncio.TimeoutError:
                            print("[AudioManager] Force killing mpg123 process")
                            self.current_process.kill()
                            await self.current_process.wait()
                
                # Start process management in background
                process_task = asyncio.create_task(manage_process())
                
                # Wait for actual audio duration (the key fix)
                await asyncio.sleep(max_wait)
                
                # Cancel process management task if still running
                if not process_task.done():
                    process_task.cancel()
                    try:
                        await process_task
                    except asyncio.CancelledError:
                        pass
                
                await asyncio.sleep(0.7)  # Buffer time for audio device release
                
            except FileNotFoundError:
                print("\n" + "*"*70)
                print("[FATAL ERROR] `mpg123` is not installed or not in /usr/bin/.")
                print("Please install it to fix audio playback: `sudo apt-get install mpg123`")
                print("*"*70 + "\n")
                # Do not fallback to paplay as it's the source of the issue
            except Exception as e:
                print(f"Error in play_audio: {e}")
                traceback.print_exc()
            finally:
                # Cleanup and state reset
                self.current_process = None
                async with self.state_lock:
                    self.state.is_speaking = False
                    self.state.is_playing = False
                    self.state.playback_start_time = None
                    self.state.current_audio_file = None
                    self.state.expected_duration = None
                self.audio_complete.set()

    async def stop_current_audio(self):
        """Stop currently playing audio and reset state."""
        if self.current_process and self.state.is_speaking:
            try:
                self.current_process.terminate()
                await self.current_process.wait()
            except Exception as e:
                print(f"Error stopping current audio: {e}")
            finally:
                self.current_process = None
                async with self.state_lock:
                    self.state.is_speaking = False
                    self.state.is_playing = False
                self.audio_complete.set()

    async def wait_for_audio_completion(self):
        """Wait for current audio playback to complete."""
        await self.audio_complete.wait()

    async def reset_audio_state(self):
        """Reset all audio states to initial values."""
        await self.stop_listening()
        async with self.state_lock:
            self.state = AudioManagerState()
        self.audio_complete.set()

    async def cleanup(self):
        """Clean up all audio resources."""
        await self.stop_listening()
        try:
            self.pa.terminate()
        except Exception as e:
            print(f"Error terminating PyAudio: {e}")

    def read_audio_frame(self, frame_size: Optional[int] = None) -> Optional[bytes]:
        """Read a frame of audio data from the input stream."""
        if not self.audio_stream:
            return None
        if not frame_size:
            frame_size = self.frame_length
        try:
            return self.audio_stream.read(frame_size, exception_on_overflow=False)
        except Exception:
            return None
