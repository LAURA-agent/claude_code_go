#!/usr/bin/env python3
"""
GameBoy Audio Manager - Output-only audio management without microphone input

Simplified version of AudioManager that only handles audio output for TTS and sound effects.
Removes all pyaudio/microphone dependencies for GameBoy-style Apple Watch input mode.
"""

import asyncio
import pygame
import threading
from typing import Optional
import traceback
import os


class GameBoyAudioManager:
    """
    Simplified audio manager for GameBoy mode - output only
    
    Handles TTS playback and sound effects without microphone input.
    Uses pygame for all audio output.
    """
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.is_initialized = False
        self._audio_lock = threading.Lock()
        
        # Initialize pygame mixer for audio output
        try:
            pygame.mixer.pre_init(frequency=sample_rate, size=-16, channels=2, buffer=1024)
            pygame.mixer.init()
            self.is_initialized = True
            print(f"[GAMEBOY_AUDIO] Audio output initialized at {sample_rate}Hz")
        except Exception as e:
            print(f"[GAMEBOY_AUDIO] Failed to initialize audio: {e}")
            self.is_initialized = False
    
    async def initialize_input(self):
        """No-op for GameBoy mode - no input needed"""
        print("[GAMEBOY_AUDIO] Input initialization skipped (GameBoy mode)")
        pass
    
    async def play_audio(self, audio_file_path: str, volume: float = 1.0):
        """Play audio file using pygame"""
        if not self.is_initialized:
            print(f"[GAMEBOY_AUDIO] Audio not initialized, skipping: {audio_file_path}")
            return
            
        if not os.path.exists(audio_file_path):
            print(f"[GAMEBOY_AUDIO] Audio file not found: {audio_file_path}")
            return
            
        try:
            with self._audio_lock:
                print(f"[GAMEBOY_AUDIO] Playing audio: {os.path.basename(audio_file_path)}")
                
                # Load and play the audio file
                pygame.mixer.music.load(audio_file_path)
                pygame.mixer.music.set_volume(volume)
                pygame.mixer.music.play()
                
                # Wait for playback to complete
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)
                    
                print(f"[GAMEBOY_AUDIO] Completed playback: {os.path.basename(audio_file_path)}")
                
        except Exception as e:
            print(f"[GAMEBOY_AUDIO] Error playing audio {audio_file_path}: {e}")
            traceback.print_exc()
    
    async def stop_audio(self):
        """Stop currently playing audio"""
        if self.is_initialized:
            try:
                with self._audio_lock:
                    pygame.mixer.music.stop()
                    print("[GAMEBOY_AUDIO] Audio playback stopped")
            except Exception as e:
                print(f"[GAMEBOY_AUDIO] Error stopping audio: {e}")
    
    def is_playing(self) -> bool:
        """Check if audio is currently playing"""
        if not self.is_initialized:
            return False
        try:
            return pygame.mixer.music.get_busy()
        except:
            return False
    
    async def cleanup(self):
        """Clean up audio resources"""
        print("[GAMEBOY_AUDIO] Cleaning up audio resources")
        try:
            if self.is_initialized:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
                self.is_initialized = False
        except Exception as e:
            print(f"[GAMEBOY_AUDIO] Error during cleanup: {e}")
    
    # Compatibility methods for existing AudioManager interface
    async def initialize(self):
        """Compatibility method - already initialized in __init__"""
        pass
    
    def get_sample_rate(self) -> int:
        """Get the configured sample rate"""
        return self.sample_rate
    
    def is_input_available(self) -> bool:
        """Always False for GameBoy mode - no microphone input"""
        return False
    
    def is_output_available(self) -> bool:
        """Check if audio output is available"""
        return self.is_initialized