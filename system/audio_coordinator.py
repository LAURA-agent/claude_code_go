#!/usr/bin/env python3

import asyncio
import os
import tempfile
import time
from pathlib import Path
from config.client_config import KEEP_TEMP_AUDIO_FILES


class AudioCoordinator:
    """
    Coordinates audio operations including TTS playback and audio completion waiting.
    
    Handles TTS audio file management, playback coordination, and proper
    timing for audio device release to prevent feedback loops.
    """
    
    def __init__(self, audio_manager):
        self.audio_manager = audio_manager
        self.is_playing_tts = False
        self.wake_word_suppression_callback = None
        
    def set_wake_word_suppression_callback(self, callback):
        """Set callback to enable/disable wake word detection during TTS"""
        self.wake_word_suppression_callback = callback

    async def handle_tts_playback(self, audio_bytes: bytes, source_engine: str):
        """
        Handle TTS audio playback by writing bytes to file and playing through AudioManager.

        This method writes the TTS audio bytes to a temporary file and ensures it
        plays completely before returning. It handles file cleanup after playback.

        Args:
            audio_bytes: The audio data from TTS engine
            source_engine: The TTS engine that generated the audio (for file extension)
        """
        if not audio_bytes:
            print("[AudioCoordinator.handle_tts_playback] No audio bytes to play.")
            return

        temp_dir = Path(tempfile.gettempdir())
        # Use .wav for Piper as it produces WAV or similar PCM output, MP3 for ElevenLabs/Cartesia.
        ext = ".wav" if source_engine.lower() in ["piper"] else ".mp3"
        fname = temp_dir / f"assistant_response_{int(time.time()*1000)}{ext}"

        try:
            # Write the TTS audio bytes to temporary file
            with open(fname, "wb") as f:
                f.write(audio_bytes)
            print(f"[AudioCoordinator.handle_tts_playback] Audio file written: {fname} ({len(audio_bytes)} bytes)")

            # Suppress wake words during TTS playback
            self.is_playing_tts = True
            if self.wake_word_suppression_callback:
                self.wake_word_suppression_callback(True)
                
            # Play the audio file directly using AudioManager.
            await self.audio_manager.play_audio(str(fname))

            print(f"[AudioCoordinator.handle_tts_playback] Audio playback completed for: {fname}")
            
            # Re-enable wake words after TTS completes
            self.is_playing_tts = False
            if self.wake_word_suppression_callback:
                self.wake_word_suppression_callback(False)

        except Exception as e:
            print(f"[ERROR] AudioCoordinator.handle_tts_playback: Failed to play audio from {fname}: {e}")
        finally:
            # Clean up temporary file after playback is confirmed complete
            if os.path.exists(fname) and not KEEP_TEMP_AUDIO_FILES:
                try:
                    os.remove(fname)
                    print(f"[AudioCoordinator.handle_tts_playback] Temp audio file deleted: {fname}")
                except Exception as e_del:
                    print(f"[WARN] Failed to delete temp audio file {fname}: {e_del}")

    async def play_audio_file(self, audio_file_path: str):
        """Play an audio file directly through the audio manager"""
        await self.audio_manager.play_audio(audio_file_path)
    
    async def play_phase_sound(self, phase: str, sound_file: str = None):
        """Play sound for specific workflow phase via TTS server"""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'http://localhost:5000/play_phase_sound',
                    json={'phase': phase, 'sound_file': sound_file}
                ) as response:
                    result = await response.json()
                    print(f"[AudioCoordinator] Phase sound {phase}: {result.get('status')}")
                    return result
        except Exception as e:
            print(f"[AudioCoordinator] Failed to play phase sound: {e}")
            # Fallback to local playback
            if sound_file:
                await self.play_audio_file(sound_file)

    async def wait_for_audio_completion_with_buffer(self):
        """Wait for audio completion with additional buffer time to ensure device release"""
        # First wait for the audio manager's completion event
        await self.audio_manager.wait_for_audio_completion()
        
        # Add a small fixed buffer to ensure audio device is fully released
        buffer_time = 0.5  # Half second buffer regardless of audio length
        await asyncio.sleep(buffer_time)

    async def stop_current_audio(self):
        """Stop any currently playing audio"""
        await self.audio_manager.stop_current_audio()

    async def wait_for_audio_completion(self):
        """Standard audio completion wait without additional buffer"""
        await self.audio_manager.wait_for_audio_completion()

    async def cleanup(self):
        """Clean up audio coordinator resources"""
        # Audio manager cleanup is handled by the audio manager itself
        pass