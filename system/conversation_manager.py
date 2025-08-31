#!/usr/bin/env python3

import asyncio
import re
from pathlib import Path
from typing import Optional


class ConversationManager:
    """
    Manages conversation flow, hooks, and follow-up interactions.
    
    Handles the logic for determining when conversations should continue,
    processing follow-up responses, and coordinating with other system components.
    """
    
    def __init__(self, speech_processor, audio_coordinator, tts_handler, client_settings):
        self.speech_processor = speech_processor
        self.audio_coordinator = audio_coordinator
        self.tts_handler = tts_handler
        self.client_settings = client_settings
        
        # Conversation continuation phrases
        self.continuation_phrases = [
            "let me know", "tell me more", "what else", "anything else",
            "can i help you with anything else", "do you need more information",
            "share your thoughts", "i'm listening", "go ahead",
            "feel free to elaborate", "i'd like to hear more", "please continue",
            "what do you think", "how does that sound", "what's next",
            ".",
        ]

    def has_conversation_hook(self, response_text):
        """Check if response has conversation hook"""
        if not response_text or not isinstance(response_text, str): 
            return False
            
        if "?" in response_text or "!" in response_text or "[continue]" in response_text.lower(): 
            return True
            
        for phrase in self.continuation_phrases:
            if phrase in response_text.lower(): 
                return True
        
        return False

    def reset_conversation_state(self):
        """Reset any lingering conversation state to prevent interference"""
        # Clear any internal state that might affect subsequent operations
        if hasattr(self, 'last_response'):
            self.last_response = None
        if hasattr(self, 'conversation_active'):
            self.conversation_active = False
        print("[ConversationManager] State reset for clean slate")

    def _clean_text_for_tts(self, text_from_server: str, mood_from_server: str | None) -> str:
        """Clean text for TTS playback"""
        if not text_from_server:
            return ""
            
        cleaned_text = text_from_server
        mood_match = re.match(r'^\[(.*?)\]([\s\S]*)', cleaned_text, re.IGNORECASE | re.DOTALL)
        
        if mood_match:
            cleaned_text = mood_match.group(2).strip()
            
        formatted_message = cleaned_text.replace('\n', ' ').strip()
        return formatted_message

    def _get_random_audio(self, category: str, subtype: str = None):
        """Get random audio file for given category"""
        import random
        try:
            base_sound_dir = "/home/user/rp_client/assets/sounds/laura"
            
            if category == "wake" and subtype in ["Laura.pmdl", "Wake_up_Laura.pmdl", "GD_Laura.pmdl"]:
                context_map = {
                    "Laura.pmdl": "standard",
                    "Wake_up_Laura.pmdl": "sleepy", 
                    "GD_Laura.pmdl": "frustrated"
                }
                folder = context_map.get(subtype, "standard")
                audio_path = Path(f"{base_sound_dir}/wake_sentences/{folder}")
            else:
                audio_path = Path(f"{base_sound_dir}/{category}_sentences")
                if subtype and (Path(f"{audio_path}/{subtype}")).exists():
                    audio_path = Path(f"{audio_path}/{subtype}")
            
            audio_files = []
            if audio_path.exists():
                audio_files = list(audio_path.glob('*.mp3')) + list(audio_path.glob('*.wav'))
            
            if audio_files:
                return str(random.choice(audio_files))
            return None
        except Exception as e:
            print(f"Error in _get_random_audio: {str(e)}")
            return None

    async def handle_conversation_loop(self, initial_response, display_manager, mcp_session, system_command_manager):
        """Handle ongoing conversation with follow-ups"""
        res = initial_response
        
        while self.has_conversation_hook(res.get("text") if isinstance(res, dict) else res):
            # Initialize audio for follow-up
            await self.speech_processor.audio_manager.initialize_input()
            # Capture follow-up speech using VAD mode
            follow_up = await self.speech_processor.capture_speech_with_unified_vad(display_manager, is_follow_up=True)
            
            if follow_up:
                # Check for system commands first
                is_cmd, cmd_type, cmd_arg = system_command_manager.detect_system_command(follow_up)
                if is_cmd:
                    await system_command_manager.handle_system_command(cmd_type, cmd_arg, mcp_session, self.tts_handler, self.audio_coordinator)
                    await display_manager.update_display('listening')
                    continue
                        
                # Process normal response
                await display_manager.update_display('thinking')
                res = await mcp_session.send_to_server(follow_up)
                
                if res and res.get("text"):
                    response_text = res.get("text")
                    mood = res.get("mood", "casual")
                    
                    cleaned_tts_text = self._clean_text_for_tts(response_text, mood)
                    await display_manager.update_display("speaking", mood=mood, text=response_text)
                    
                    # Handle TTS
                    if self.client_settings.get("tts_mode") != "text" and cleaned_tts_text:
                        audio_bytes, engine = await self.tts_handler.generate_audio(cleaned_tts_text, persona_name="laura")
                        if audio_bytes:
                            await self.audio_coordinator.handle_tts_playback(audio_bytes, engine)
                    else:
                        print(f"Assistant: {response_text}")
                        await asyncio.sleep(0.1 * len(cleaned_tts_text.split()) if cleaned_tts_text else 1)
                    
                    if not self.has_conversation_hook(response_text):
                        await self.audio_coordinator.wait_for_audio_completion_with_buffer()
                        await display_manager.update_display("idle")
                        break
                    
                    await self.audio_coordinator.wait_for_audio_completion_with_buffer()
                    await display_manager.update_display('listening')
                else:
                    await display_manager.update_display("error", text="Server Error")
                    await asyncio.sleep(2)
                    break
            else:
                # No follow-up detected, play timeout message
                timeout_audio = self._get_random_audio("timeout")
                if timeout_audio:
                    await self.audio_coordinator.play_audio_file(timeout_audio)
                else:
                    cleaned_text = "No input detected. Feel free to ask for assistance when needed"
                    audio_bytes, engine = await self.tts_handler.generate_audio(cleaned_text, persona_name="laura")
                    if audio_bytes:
                        await self.audio_coordinator.handle_tts_playback(audio_bytes, engine)
                await self.audio_coordinator.wait_for_audio_completion_with_buffer()
                await display_manager.update_display('idle')
                break

    async def process_initial_response(self, response, display_manager, mcp_session, system_command_manager):
        """Process the initial server response and handle conversation flow"""
        print(f"[DEBUG] process_initial_response called with: {response}")
        if response and response.get("text"):
            response_text = response.get("text")
            mood = response.get("mood", "casual")
            print(f"[DEBUG] Extracted response_text: '{response_text}', mood: '{mood}'")
            
            cleaned_tts_text = self._clean_text_for_tts(response_text, mood)
            await display_manager.update_display("speaking", mood=mood, text=response_text)
            
            # Print response
            print(f"\nAssistant: {response_text}")
            print(f"[DEBUG] Console logging executed successfully")
            
            # Handle TTS
            if self.client_settings.get("tts_mode") != "text" and cleaned_tts_text:
                audio_bytes, engine = await self.tts_handler.generate_audio(cleaned_tts_text, persona_name="laura")
                if audio_bytes:
                    await self.audio_coordinator.handle_tts_playback(audio_bytes, engine)
            else:
                await asyncio.sleep(0.1 * len(cleaned_tts_text.split()) if cleaned_tts_text else 1)
            
            # Check for conversation continuation
            if self.has_conversation_hook(response_text):
                await self.audio_coordinator.wait_for_audio_completion_with_buffer()
                await display_manager.update_display('listening')
                await self.handle_conversation_loop(response_text, display_manager, mcp_session, system_command_manager)
            else:
                await self.audio_coordinator.wait_for_audio_completion_with_buffer()
                await display_manager.update_display("idle")
        else:
            await display_manager.update_display("error", text="Server Error")
            await asyncio.sleep(2)
            await display_manager.update_display("idle")