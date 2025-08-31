#!/usr/bin/env python3

import asyncio
import base64
from pathlib import Path
from typing import Optional, Tuple
from system.client_system_manager import ClientSystemManager


class SystemCommandManager:
    """
    Manages system command detection and execution.
    
    Handles detection of system commands in transcripts, command execution,
    and coordination with TTS and audio systems for feedback.
    """
    
    def __init__(self, client_settings, save_client_settings_func, 
                 get_active_tts_provider_func, set_active_tts_provider_func):
        self.client_settings = client_settings
        self.save_client_settings = save_client_settings_func
        self.get_active_tts_provider = get_active_tts_provider_func
        self.set_active_tts_provider = set_active_tts_provider_func
        self.system_manager = ClientSystemManager()

    def detect_system_command(self, transcript: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Detect system commands in transcript"""
        t = transcript.lower()
        if "enable remote tts" in t or "api tts" in t:
            return True, "switch_tts_mode", "api"
        elif "enable local tts" in t or "local tts" in t:
            return True, "switch_tts_mode", "local"
        elif "text only mode" in t or "text only" in t:
            return True, "switch_tts_mode", "text"
        elif "switch tts provider to cartesia" in t:
            return True, "switch_api_tts_provider", "cartesia"
        elif "switch tts provider to elevenlabs" in t:
            return True, "switch_api_tts_provider", "elevenlabs"
        elif "switch tts provider to piper" in t:
            return True, "switch_api_tts_provider", "piper"
        elif "calibrate the microphone" in t or "run voice calibration" in t or "calibrate voice detection" in t or "calibrate microphone" in t:
            return True, "vad_calibration", None
        elif "claude code voice" in t or "voice coding" in t or "start voice input" in t:
            return True, "claude_code_voice", None
        # Test notification commands
        elif "test notification" in t or "test medicine reminder" in t:
            return True, "test_notification", "medicine_reminder"
        elif "test notification late" in t or "test late reminder" in t:
            return True, "test_notification_late", "medicine_reminder_late"
        # Reminder acknowledgment commands
        elif any(phrase in t for phrase in ["i took my medicine", "took my medicine", "medicine taken", "i took it"]):
            return True, "clear_reminder", "medicine"
        elif any(phrase in t for phrase in ["i'm going to bed", "going to bed", "bedtime", "time for bed"]):
            return True, "clear_reminder", "bedtime"
        elif any(phrase in t for phrase in ["i exercised", "workout done", "finished exercising", "exercise complete"]):
            return True, "clear_reminder", "exercise"
        elif any(phrase in t for phrase in ["reminder done", "finished that", "task complete", "i did it"]):
            return True, "clear_reminder", "general"
        # Demo mode command
        elif "demo mode" in t or "demonstration mode" in t or "show demo" in t:
            return True, "demo_mode", None
        return False, None, None

    async def upload_document(self, file_path: str, mcp_session, session_id) -> dict | None:
        """Upload document to server"""
        if not mcp_session or not session_id: 
            return None
            
        try:
            with open(file_path, 'rb') as f: 
                content = base64.b64encode(f.read()).decode('utf-8')
                
            return await mcp_session.call_tool("upload_document", arguments={
                "session_id": session_id, 
                "filename": Path(file_path).name, 
                "content": content
            })
        except Exception as e:
            print(f"[ERROR] Document upload failed: {e}")
            return None

    async def handle_system_command(self, cmd_type, cmd_arg, mcp_session, tts_handler, audio_coordinator, display_manager=None):
        """Handle system commands with audio feedback"""
        print(f"[INFO] System command: {cmd_type}('{cmd_arg}')")
        
        uploaded_count = 0
        pending_files = []
        processed_files = []
        
        if cmd_type == "clear_reminder":
            # Use ClientSystemManager for reminder clearing
            success = await self.system_manager.clear_reminder(cmd_arg, mcp_session, None)
            return
        elif cmd_type == "test_notification":
            print("[INFO] Triggering test notification...")
            # Import notification manager from run_v2 context
            if hasattr(self, '_notification_manager'):
                await self._notification_manager.test_local_notification(display_manager, "medicine_reminder", 0)
            else:
                print("[WARNING] Notification manager not available for testing")
            return
        elif cmd_type == "test_notification_late":
            print("[INFO] Triggering test late notification...")
            if hasattr(self, '_notification_manager'):
                await self._notification_manager.test_local_notification(display_manager, "medicine_reminder", 25)
            else:
                print("[WARNING] Notification manager not available for testing")
            return
        elif cmd_type == "switch_tts_mode":
            self.client_settings["tts_mode"] = cmd_arg
        elif cmd_type == "switch_api_tts_provider":
            self.set_active_tts_provider(cmd_arg)
        elif cmd_type == "claude_code_voice":
            print("[INFO] Starting Claude Code voice input...")
            # Switch to Claude Code display profile
            if display_manager:
                display_manager.set_display_profile('claude_code')
            # Launch voice input for Claude Code
            try:
                from claude.voice_input_manager import VoiceInputManager
                voice_manager = VoiceInputManager()
                
                # Send TTS notification
                await tts_handler.generate_audio("Starting Claude Code voice input. Speak now.", persona_name="laura")
                
                # Start voice capture
                result = await voice_manager.capture_voice_for_clipboard(duration=60)
                
                if result:
                    response_text = "Voice input captured and copied to clipboard. You can now paste it into Claude Code."
                else:
                    response_text = "No speech detected for Claude Code voice input."
                    
                audio_bytes, engine = await tts_handler.generate_audio(response_text, persona_name="laura")
                if audio_bytes:
                    await audio_coordinator.handle_tts_playback(audio_bytes, engine)
                    
            except Exception as e:
                print(f"[ERROR] Claude Code voice input failed: {e}")
                
        elif cmd_type == "demo_mode":
            print("[INFO] Entering demo mode...")
            # Load the demo documentation
            demo_file = Path("/home/user/rp_client/GPI_CASE2_SYSTEM_DEMO.md")
            if demo_file.exists():
                # Send notification that demo mode is active
                response_text = "Demo mode activated. I can now answer questions about the GPi Case 2 system transformation, including hardware modifications, software architecture, and development stories."
                audio_bytes, engine = await tts_handler.generate_audio(response_text, persona_name="claude")
                if audio_bytes:
                    await audio_coordinator.handle_tts_playback(audio_bytes, engine)
                print("[INFO] Demo mode active - using GPI_CASE2_SYSTEM_DEMO.md as context")
            else:
                response_text = "Demo mode documentation not found. Please ensure the system demo file exists."
                audio_bytes, engine = await tts_handler.generate_audio(response_text, persona_name="claude")
                if audio_bytes:
                    await audio_coordinator.handle_tts_playback(audio_bytes, engine)
                print("[ERROR] Demo file not found at /home/user/rp_client/GPI_CASE2_SYSTEM_DEMO.md")
            return
            
        elif cmd_type == "vad_calibration":
            print("[INFO] Starting VAD calibration...")
            # Run calibration subprocess in auto mode
            process = await asyncio.create_subprocess_exec(
                'python3', 'vad_calib.py', '--auto',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Reload VAD settings after calibration
                from config.client_config import load_client_settings
                load_client_settings()
                print("[INFO] VAD calibration complete and settings reloaded.")
            else:
                print(f"[ERROR] VAD calibration failed: {stderr.decode()}")
        
        self.save_client_settings()
        

    async def check_and_upload_documents(self, mcp_session, session_id):
        """Check for and upload any pending documents"""
        query_files_path = Path(self.client_settings.get("QUERY_FILES_DIR", "/home/user/rp_client/query_files"))
        if query_files_path.exists():
            for file_to_upload in query_files_path.iterdir():
                if file_to_upload.is_file():
                    upload_result = await self.upload_document(str(file_to_upload), mcp_session, session_id)
                    
                    # Move to offload directory
                    offload_path = Path(self.client_settings.get("QUERY_OFFLOAD_DIR", "/home/user/rp_client/query_offload"))
                    offload_path.mkdir(parents=True, exist_ok=True)
                    
                    try:
                        file_to_upload.rename(offload_path / file_to_upload.name)
                        print(f"[INFO] Document {file_to_upload.name} uploaded and moved to offload")
                    except Exception as e:
                        print(f"[ERROR] Could not move {file_to_upload.name}: {e}")
