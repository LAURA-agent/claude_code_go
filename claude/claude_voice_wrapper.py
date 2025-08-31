#!/usr/bin/env python3
"""
Claude Code Voice Wrapper
Launches Claude Code CLI with voice input using STT/VAD from RP500-Client
"""

import asyncio
import subprocess
import sys
import os
import json
import threading
import queue
from pathlib import Path

# Add RP500-Client to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audio_manager import AudioManager
from vosk_websocket_client import VoskTranscriber
from speech_processor import SpeechProcessor
from system.vad_settings import load_vad_settings
from config.client_config import VOSK_MODEL_PATH, AUDIO_SAMPLE_RATE
from claude_tts_notifier import tts_notifier


class ClaudeVoiceWrapper:
    def __init__(self):
        self.audio_manager = AudioManager(sample_rate=AUDIO_SAMPLE_RATE)
        self.transcriber = VoskTranscriber(sample_rate=AUDIO_SAMPLE_RATE)
        self.vad_settings = load_vad_settings()
        self.speech_processor = SpeechProcessor(
            self.audio_manager,
            self.transcriber,
            self.vad_settings
        )
        self.claude_process = None
        self.output_queue = queue.Queue()
        
    def start_claude_code(self):
        """Start Claude Code CLI in interactive mode"""
        print("🚀 Starting Claude Code CLI...")
        self.claude_process = subprocess.Popen(
            ['claude'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Start thread to read Claude's output
        output_thread = threading.Thread(target=self._read_claude_output)
        output_thread.daemon = True
        output_thread.start()
        
        # Wait for Claude to be ready
        self._wait_for_claude_ready()
        
    def _read_claude_output(self):
        """Read output from Claude process"""
        while self.claude_process and self.claude_process.poll() is None:
            try:
                line = self.claude_process.stdout.readline()
                if line:
                    print(line, end='')  # Print to console
                    self.output_queue.put(line)
            except:
                break
                
    def _wait_for_claude_ready(self):
        """Wait for Claude to show it's ready for input"""
        print("⏳ Waiting for Claude Code to be ready...")
        ready_indicators = ["claude>", ">>>", "Ready", "Type"]
        
        timeout = 10  # seconds
        start_time = asyncio.get_event_loop().time()
        
        while True:
            try:
                line = self.output_queue.get(timeout=0.1)
                if any(indicator in line for indicator in ready_indicators):
                    print("✅ Claude Code is ready!")
                    break
            except queue.Empty:
                if asyncio.get_event_loop().time() - start_time > timeout:
                    print("⚠️ Timeout waiting for Claude Code")
                    break
                    
    def send_to_claude(self, text):
        """Send text to Claude Code CLI"""
        if self.claude_process and self.claude_process.poll() is None:
            print(f"\n📝 Sending to Claude: {text}")
            self.claude_process.stdin.write(text + '\n')
            self.claude_process.stdin.flush()
        else:
            print("❌ Claude process is not running")
            
    async def capture_voice_input(self):
        """Capture voice input using VAD/STT"""
        print("\n🎤 Listening... (Press Left Meta to stop)")
        
        # Initialize audio
        await self.audio_manager.initialize_input()
        
        # Capture speech with VAD
        audio_frames, stats = await self.speech_processor.capture_speech_with_unified_vad(
            manual_stop_event=None  # Could add keyboard event handling
        )
        
        if audio_frames:
            # Process with STT
            self.transcriber.reset()
            for frame in audio_frames:
                self.transcriber.process_frame(frame)
                
            text = self.transcriber.get_final_text()
            
            if text:
                print(f"🗣️ Transcribed: {text}")
                return text
            else:
                print("❌ No speech detected")
                return None
        else:
            print("❌ No audio captured")
            return None
            
    async def run_interactive_mode(self):
        """Run in interactive mode with continuous voice input"""
        print("\n🎙️ Claude Code Voice Wrapper - Interactive Mode")
        print("Say 'exit' or 'quit' to stop")
        print("-" * 50)
        
        # Start Claude Code
        self.start_claude_code()
        
        try:
            while True:
                # Capture voice input
                text = await self.capture_voice_input()
                
                if text:
                    # Check for exit commands
                    if text.lower() in ['exit', 'quit', 'stop', 'goodbye']:
                        print("\n👋 Exiting...")
                        break
                        
                    # Send to Claude
                    self.send_to_claude(text)
                    
                    # Give Claude time to process and respond
                    await asyncio.sleep(2)
                    
                # Small delay between captures
                await asyncio.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user")
        finally:
            self.cleanup()
            
    async def run_single_query(self, query=None):
        """Run with a single voice query"""
        print("\n🎙️ Claude Code Voice Wrapper - Single Query Mode")
        
        # Start Claude Code
        self.start_claude_code()
        
        try:
            # Get voice input if no query provided
            if not query:
                query = await self.capture_voice_input()
                
            if query:
                # Send to Claude
                self.send_to_claude(query)
                
                # Wait for response (simple timeout-based approach)
                print("\n⏳ Waiting for Claude's response...")
                await asyncio.sleep(5)  # Adjust based on typical response time
                
                # Could add TTS notification when done
                tts_notifier.update_status("Claude has finished processing your request")
                
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user")
        finally:
            # Keep Claude running for manual interaction
            print("\n💡 Claude Code is still running. You can continue typing manually.")
            print("Press Ctrl+C again to fully exit.")
            try:
                # Wait for user to exit
                while self.claude_process.poll() is None:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                self.cleanup()
                
    def cleanup(self):
        """Clean up resources"""
        print("\n🧹 Cleaning up...")
        
        # Stop audio
        if hasattr(self.audio_manager, 'stream') and self.audio_manager.stream:
            self.audio_manager.stop_listening()
            
        # Terminate Claude process
        if self.claude_process:
            self.claude_process.terminate()
            self.claude_process.wait(timeout=5)
            
        print("✅ Cleanup complete")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Voice Wrapper")
    parser.add_argument(
        '--mode', 
        choices=['interactive', 'single'],
        default='single',
        help='Run mode: interactive (continuous) or single (one query)'
    )
    parser.add_argument(
        '--query',
        type=str,
        help='Optional query text (skips voice capture)'
    )
    
    args = parser.parse_args()
    
    wrapper = ClaudeVoiceWrapper()
    
    if args.mode == 'interactive':
        await wrapper.run_interactive_mode()
    else:
        await wrapper.run_single_query(args.query)


if __name__ == "__main__":
    asyncio.run(main())