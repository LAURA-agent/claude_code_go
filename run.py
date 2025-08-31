#!/usr/bin/env python3

import asyncio
import json
import os
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from colorama import Fore, Style, init
from aiohttp import web
import aiohttp
import requests
from mutagen.mp3 import MP3

# MCP Imports
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

# Local Component Imports
from system.gameboy_audio_manager import GameBoyAudioManager as AudioManager
from communication.client_tts_handler import TTSHandler
from communication.mcp_notification_handler import NotificationClientSession
# VOSK transcriber removed for GameBoy-style Apple Watch input
from display.display_manager import DisplayManager

# New Modular Components
from speech_capture.speech_processor import SpeechProcessor
from system.conversation_manager import ConversationManager
from system.input_manager import InputManager
from system.notification_manager import NotificationManager
from system.system_command_manager import SystemCommandManager
from system.audio_coordinator import AudioCoordinator

# Configuration and Utilities
from config.client_config import (
    SERVER_URL, DEVICE_ID, AUDIO_SAMPLE_RATE,
    client_settings, save_client_settings, get_active_tts_provider, set_active_tts_provider
)
# VOSK readiness checker removed for GameBoy-style Apple Watch input

# Initialize colorama
init()


def get_random_audio(category: str, subtype: str = None):
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
        print(f"Error in get_random_audio: {str(e)}")
        return None


class PiMCPClient:
    """
    Modular MCP Client for Pi 500 with clean separation of concerns.
    
    This orchestrator coordinates between all the specialized managers
    while maintaining a minimal footprint for the main client logic.
    """
    
    def __init__(self, server_url: str, device_id: str):
        self.server_url = server_url
        self.device_id = device_id
        self.session_id: str | None = None
        self.mcp_session: ClientSession | None = None
        
        # Initialize core components
        self.audio_manager = AudioManager(sample_rate=AUDIO_SAMPLE_RATE)
        self.tts_handler = TTSHandler()
        self.display_manager = DisplayManager(
            svg_path=client_settings.get("DISPLAY_SVG_PATH"),
            window_size=client_settings.get("DISPLAY_WINDOW_SIZE")
        )
        
        # Initialize Claude Code TTS coordination
        from claude.claude_tts_notifier import tts_notifier
        tts_notifier.set_display_manager(self.display_manager)
        
        # Transcriber removed for GameBoy-style Apple Watch input
        self.transcriber = None
        
        # Initialize specialized managers
        self.input_manager = InputManager(self.audio_manager)
        self.audio_coordinator = AudioCoordinator(self.audio_manager)
        # Speech processor removed for GameBoy-style Apple Watch input
        self.speech_processor = None
        self.conversation_manager = ConversationManager(
            None,  # speech_processor removed for Apple Watch input
            self.audio_coordinator,
            self.tts_handler,
            client_settings
        )
        self.notification_manager = NotificationManager(
            self.audio_coordinator,
            self.tts_handler
        )
        self.system_command_manager = SystemCommandManager(
            client_settings,
            save_client_settings,
            get_active_tts_provider,
            set_active_tts_provider
        )
        
        # Provide notification manager reference for testing commands
        self.system_command_manager._notification_manager = self.notification_manager
        
        # Keyboard initialization simplified for GameBoy-style input
        self.input_manager.initialize_keyboard()

    async def initialize_session(self):
        """Initialize the client session with the MCP server"""
        try:
            if not self.mcp_session:
                print("[ERROR] MCP session object not available for registration.")
                return False
                
            print("[INFO] Performing MCP handshake with server...")
            await self.mcp_session.initialize()
            print("[INFO] MCP handshake completed successfully.")
            
            await asyncio.sleep(2.0)  # Give server time to be ready

            registration_payload = {
                "device_id": self.device_id,
                "capabilities": {
                    "input": ["text", "audio"],
                    "output": ["text", "audio"],
                    "tts_mode": client_settings.get("tts_mode", "api"),
                    "api_tts_provider": get_active_tts_provider(),
                    "supports_caching": True
                }
            }
            
            print(f"[INFO] Calling 'register_device' tool with payload: {registration_payload}")
            response_obj = await self.mcp_session.call_tool("register_device", arguments=registration_payload)

            if hasattr(response_obj, 'content') and response_obj.content:
                text_content = response_obj.content[0].text
                response_data = json.loads(text_content)
            else:
                response_data = response_obj

            if isinstance(response_data, dict) and response_data.get("session_id"):
                self.session_id = response_data["session_id"]
                print(f"[INFO] Device registration successful. Session ID: {self.session_id}")
                return True
            else:
                print(f"[ERROR] Device registration failed. Response: {response_data}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Error during session initialization: {e}")
            traceback.print_exc()
            return False

    async def send_to_server(self, transcript: str) -> dict | None:
        """Send text to MCP server and get response"""
        if not self.session_id or not self.mcp_session:
            print("[ERROR] Session not initialized. Cannot send message.")
            return {"text": "Error: Client session not ready.", "mood": "error"}
        
        # Filter out short transcripts (2 words or less)
        word_count = len(transcript.strip().split())
        if word_count <= 2:
            print(f"[INFO] Rejecting short transcript ({word_count} word{'s' if word_count != 1 else ''}): '{transcript}'")
            return None
            
        try:
            tool_call_args = {
                "session_id": self.session_id,
                "input_type": "text",
                "payload": {"text": transcript},
                "output_mode": ["text", "audio"],
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            print(f"[INFO] Calling 'run_LAURA' tool...")
            
            # Create a task for the MCP call so we can monitor it
            mcp_task = asyncio.create_task(
                self.mcp_session.call_tool("run_LAURA", arguments=tool_call_args)
            )
            
            # Monitor the task with periodic status updates
            elapsed = 0
            while not mcp_task.done():
                await asyncio.sleep(5)  # Check every 5 seconds
                elapsed += 5
                
                if elapsed == 10:
                    print("[INFO] Server is processing (10 seconds)...")
                    # Play a subtle ping to indicate still waiting
                    try:
                        ping_sound = "/home/user/rp_client/assets/sounds/sound_effects/radarping.mp3"
                        if os.path.exists(ping_sound):
                            self.audio_manager.play_audio_file(ping_sound)
                    except:
                        pass
                elif elapsed == 20:
                    print("[INFO] Server still processing (20 seconds)...")
                elif elapsed == 30:
                    print("[INFO] Complex request detected (30 seconds)...")
                    # Notify user of long operation
                    try:
                        subprocess.run(['python3', '/home/user/rp_client/TTS/speak.py', '--working', 
                                      'Still processing your request'], capture_output=True)
                    except:
                        pass
                elif elapsed >= 60 and elapsed % 30 == 0:
                    print(f"[INFO] Extended processing ({elapsed} seconds)...")
            
            # Get the result when complete
            response_payload = await mcp_task
            
            # Parse response properly
            parsed_response = None
            if hasattr(response_payload, 'content') and response_payload.content:
                json_str = response_payload.content[0].text
                parsed_response = json.loads(json_str)
            elif isinstance(response_payload, dict):
                parsed_response = response_payload
            else:
                print(f"[ERROR] Unexpected response format: {type(response_payload)}")
                return {"text": "Sorry, I received an unexpected response format.", "mood": "confused"}

            if isinstance(parsed_response, dict) and "text" in parsed_response:
                return parsed_response
            else:
                print(f"[ERROR] Invalid response: {parsed_response}")
                return {"text": "Sorry, I received an unexpected response.", "mood": "confused"}
                
        except (ConnectionError, ConnectionRefusedError, OSError) as e:
            print(f"[ERROR] Connection lost during server call: {e}")
            # Clear session to trigger reconnection
            self.mcp_session = None
            self.session_id = None
            return {"text": "Connection lost. Reconnecting...", "mood": "error"}
        except Exception as e:
            print(f"[ERROR] Failed to call server: {e}")
            traceback.print_exc()
            return {"text": "Sorry, a communication problem occurred.", "mood": "error"}

    async def run_main_loop(self):
        """Simplified GameBoy-style main loop - waits for Apple Watch input"""
        print("[INFO] GameBoy-style main loop started - waiting for Apple Watch input.")
        
        while True:
            try:
                current_state = self.display_manager.current_state
                
                # Simple state monitoring - just check for sleep timeout
                if current_state == 'idle':
                    time_since_interaction = self.input_manager.get_time_since_last_interaction()
                    
                    # Sleep timeout (5 minutes)
                    if time_since_interaction >= 300:  # 5 minutes
                        print(f"[INFO] Sleep timeout reached ({time_since_interaction:.1f}s since last interaction)")
                        await self.display_manager.update_display('sleep')
                
                # All conversation processing now happens via handle_apple_watch_input()
                # which is called from the HTTP endpoint
                
                await asyncio.sleep(1)  # Simple 1-second sleep loop
                    
            except Exception as e:
                print(f"[ERROR] Error in main loop: {e}")
                traceback.print_exc()
                await self.display_manager.update_display("error", text="System Error")
                await asyncio.sleep(2)
                await self.display_manager.update_display("idle")

    async def handle_tts_conversation(self, request):
        """TTS endpoint that returns to idle state - for questions/confirmations"""
        try:
            data = await request.json()
            text = data.get('text', '')
            mood = data.get('mood', 'explaining')
            
            if text:
                # Update display to speaking with appropriate mood
                await self.display_manager.update_display("speaking", mood=mood)
                
                # Send to TTS server
                try:
                    response = requests.post(
                        "http://localhost:5000/tts",
                        headers={"Content-Type": "application/json"},
                        json={"text": text, "voice": "claude"},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        # Get exact audio duration using mutagen
                        response_data = response.json()
                        audio_file_path = response_data.get('audio_file')
                        
                        if audio_file_path and os.path.exists(audio_file_path):
                            try:
                                audio_info = MP3(audio_file_path)
                                exact_duration = audio_info.info.length
                                print(f"[TTS Conversation] Exact audio duration: {exact_duration:.2f}s")
                                await asyncio.sleep(exact_duration)
                            except Exception as mutagen_error:
                                print(f"[TTS Conversation] Mutagen error: {mutagen_error}, falling back to estimation")
                                # Fallback to estimation
                                word_count = len(text.split())
                                estimated_duration = max(2, (word_count / 150) * 60)
                                await asyncio.sleep(estimated_duration)
                        else:
                            print(f"[TTS Conversation] No audio file path returned, using estimation")
                            # Fallback to estimation  
                            word_count = len(text.split())
                            estimated_duration = max(2, (word_count / 150) * 60)
                            await asyncio.sleep(estimated_duration)
                    
                except Exception as e:
                    print(f"[TTS Error] {e}")
                
                # Return to idle state - waiting for user input
                self.input_manager.restart_wake_word_detection()
                await self.display_manager.update_display("idle")
                
            return web.json_response({"status": "success", "state": "idle"})
        except Exception as e:
            print(f"[TTS Conversation Error] {e}")
            return web.json_response({"status": "error", "error": str(e)}, status=500)
    
    async def handle_apple_watch_input(self, text: str):
        """Handle text input from Apple Watch voice injection"""
        try:
            print(f"[APPLE_WATCH] Received input: '{text}'")
            
            # Update interaction time to prevent sleep timeout
            self.input_manager.update_last_interaction()
            
            # Update to thinking state (or wake from sleep)
            await self.display_manager.update_display('thinking')
            
            # Check for system commands first
            is_cmd, cmd_type, cmd_arg = self.system_command_manager.detect_system_command(text)
            if is_cmd:
                await self.system_command_manager.handle_system_command(
                    cmd_type, cmd_arg, self.mcp_session, 
                    self.tts_handler, self.audio_coordinator, self.display_manager
                )
                await self.display_manager.update_display('idle')
                return
            
            # Check for document uploads
            await self.system_command_manager.check_and_upload_documents(self.mcp_session, self.session_id)
            
            # Show processing state with audio feedback
            await self.display_manager.update_display('execution')
            
            # Play processing sound effect
            try:
                processing_sound = "/home/user/rp_client/assets/sounds/sound_effects/data_processing.mp3"
                if os.path.exists(processing_sound):
                    self.audio_manager.play_audio_file(processing_sound)
            except Exception as e:
                print(f"[INFO] Could not play processing sound: {e}")
            
            # Process as normal conversation
            response = await self.send_to_server(text)
            
            if response is not None:
                # Handle response through conversation manager
                await self.conversation_manager.process_initial_response(
                    response, self.display_manager, self, self.system_command_manager
                )
            else:
                # Return to idle if no valid response
                await self.display_manager.update_display("idle")
                
        except Exception as e:
            print(f"[ERROR] Error handling Apple Watch input: {e}")
            await self.display_manager.update_display("error", text="Input Error")
            await asyncio.sleep(2)
            await self.display_manager.update_display("idle")
    
    async def handle_tts_working(self, request):
        """TTS endpoint that goes to execution state - for status updates while working"""
        try:
            data = await request.json()
            text = data.get('text', '')
            mood = data.get('mood', 'solution')
            
            if text:
                # Update display to speaking with appropriate mood
                await self.display_manager.update_display("speaking", mood=mood)
                
                # Send to TTS server
                try:
                    response = requests.post(
                        "http://localhost:5000/tts",
                        headers={"Content-Type": "application/json"},
                        json={"text": text, "voice": "claude"},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        # Get exact audio duration using mutagen
                        response_data = response.json()
                        audio_file_path = response_data.get('audio_file')
                        
                        if audio_file_path and os.path.exists(audio_file_path):
                            try:
                                audio_info = MP3(audio_file_path)
                                exact_duration = audio_info.info.length
                                print(f"[TTS Working] Exact audio duration: {exact_duration:.2f}s")
                                await asyncio.sleep(exact_duration)
                            except Exception as mutagen_error:
                                print(f"[TTS Working] Mutagen error: {mutagen_error}, falling back to estimation")
                                # Fallback to estimation
                                word_count = len(text.split())
                                estimated_duration = max(2, (word_count / 150) * 60)
                                await asyncio.sleep(estimated_duration)
                        else:
                            print(f"[TTS Working] No audio file path returned, using estimation")
                            # Fallback to estimation  
                            word_count = len(text.split())
                            estimated_duration = max(2, (word_count / 150) * 60)
                            await asyncio.sleep(estimated_duration)
                    
                except Exception as e:
                    print(f"[TTS Error] {e}")
                
                # Return to execution state - still working
                await self.display_manager.update_display("execution")
                
            return web.json_response({"status": "success", "state": "execution"})
        except Exception as e:
            print(f"[TTS Working Error] {e}")
            return web.json_response({"status": "error", "error": str(e)}, status=500)
    
    async def handle_apple_watch_conversation(self, request):
        """HTTP endpoint to receive Apple Watch voice input"""
        try:
            data = await request.json()
            text = data.get('text', '')
            
            if text:
                # Handle the input asynchronously
                asyncio.create_task(self.handle_apple_watch_input(text))
                return web.json_response({"status": "success", "message": "Input received"})
            else:
                return web.json_response({"status": "error", "message": "No text provided"}, status=400)
                
        except Exception as e:
            print(f"[ERROR] Apple Watch input error: {e}")
            return web.json_response({"status": "error", "error": str(e)}, status=500)
    
    async def start_tts_server(self):
        """Start the HTTP server for TTS and Apple Watch endpoints"""
        app = web.Application()
        app.router.add_post('/tts/conversation', self.handle_tts_conversation)
        app.router.add_post('/tts/working', self.handle_tts_working)
        app.router.add_post('/apple_watch/input', self.handle_apple_watch_conversation)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', 8888)
        await site.start()
        print("[INFO] TTS and Apple Watch HTTP endpoints started on localhost:8888")
        print("  - /tts/conversation: Returns to idle state")  
        print("  - /tts/working: Returns to execution state")
        print("  - /apple_watch/input: Receives Apple Watch voice input")
        return runner
    
    async def run(self):
        """Main client run loop with multi-task architecture"""
        print(f"{Fore.CYAN}PiMCPClient v2 run loop started.{Fore.WHITE}")
        await self.display_manager.update_display("boot")
        
        # Start TTS and Apple Watch HTTP server
        tts_server = await self.start_tts_server()

        # Start background tasks
        background_tasks = [
            asyncio.create_task(self.display_manager.rotate_background()),
            asyncio.create_task(self.notification_manager.check_for_notifications_loop(
                self.mcp_session, self.session_id, self.display_manager
            )),
            asyncio.create_task(self.sleep_timeout_monitor()),
        ]

        connection_attempts = 0
        handshake_failures = 0
        connection_failures = 0  # Track connection failures separately
        code_mode_active = False
        
        while True:
            try:
                # If in code mode, handle it differently
                if code_mode_active:
                    # Run main loop without server connection
                    print("[INFO] Running in code mode - server connection bypassed")
                    await self.display_manager.update_display("code")
                    
                    # Add main loop task and run it
                    main_loop_task = asyncio.create_task(self.run_main_loop())
                    all_tasks = background_tasks + [main_loop_task]
                    
                    try:
                        await asyncio.gather(*all_tasks, return_exceptions=True)
                    except Exception as e:
                        print(f"[ERROR] Task execution error in code mode: {e}")
                    finally:
                        # Cancel main loop task
                        main_loop_task.cancel()
                        try:
                            await main_loop_task
                        except asyncio.CancelledError:
                            pass
                    
                    # Check if user wants to try reconnecting (wait a bit)
                    await asyncio.sleep(10)
                    continue
                
                connection_attempts += 1
                if connection_attempts > 1:
                    print(f"[INFO] Reconnection attempt #{connection_attempts - 1}")
                print(f"[INFO] Attempting to connect to MCP server at {self.server_url}...")
                
                async with sse_client(f"{self.server_url}/events/sse", headers={}) as (read, write):
                    print("[INFO] SSE client connected. Creating ClientSession...")
                    connection_attempts = 0  # Reset counter on successful connection
                    
                    async with NotificationClientSession(
                        read, write,
                        tts_handler=self.tts_handler,
                        display_manager=self.display_manager,
                        audio_coordinator=self.audio_coordinator,
                        conversation_manager=self.conversation_manager
                    ) as session:
                        self.mcp_session = session
                        print("[INFO] NotificationClientSession active with server-push support.")

                        if not await self.initialize_session():
                            print("[ERROR] Failed to initialize session. Reconnecting...")
                            handshake_failures += 1
                            raise Exception("Session initialization failed")

                        # Reset failures on successful connection
                        handshake_failures = 0
                        connection_failures = 0
                        code_mode_active = False
                        
                        await self.display_manager.update_display("idle")
                        print(f"{Fore.CYAN}✓ Session initialized successfully{Fore.WHITE}")
                        
                        # Play startup sound and transition to sleep (only on first connection)
                        if connection_attempts == 0:
                            print(f"\n{Fore.CYAN}=== Startup Sequence ==={Fore.WHITE}")
                            startup_sound = "/home/user/rp_client/assets/sounds/sound_effects/successfulloadup.mp3"
                            if os.path.exists(startup_sound):
                                try:
                                    print(f"{Fore.CYAN}Playing startup audio...{Fore.WHITE}")
                                    # Use idle for Claude Code profile, sleep for LAURA
                                    final_state = 'idle' if self.display_manager.display_profile == 'claude_code' else 'sleep'
                                    await self.display_manager.update_display(final_state)
                                    await self.audio_coordinator.play_audio_file(startup_sound)
                                    print(f"{Fore.GREEN}✓ Startup audio complete{Fore.WHITE}")
                                except Exception as e:
                                    print(f"{Fore.YELLOW}Warning: Could not play startup sound: {e}{Fore.WHITE}")
                        else:
                            # Reconnection success - brief audio notification
                            print(f"{Fore.GREEN}✓ Reconnected to MCP server{Fore.WHITE}")
                            # Use idle for Claude Code profile, sleep for LAURA
                            final_state = 'idle' if self.display_manager.display_profile == 'claude_code' else 'sleep'
                            await self.display_manager.update_display(final_state)
                        
                        print(f"{Fore.MAGENTA}🎧 Listening for wake word or press Raspberry button to begin...{Fore.WHITE}")
                        
                        # Update notification manager with session info
                        background_tasks[1].cancel()
                        background_tasks[1] = asyncio.create_task(
                            self.notification_manager.check_for_notifications_loop(
                                self.mcp_session, self.session_id, self.display_manager
                            )
                        )
                        
                        # Add main loop to tasks and run all concurrently
                        main_loop_task = asyncio.create_task(self.run_main_loop())
                        all_tasks = background_tasks + [main_loop_task]
                        
                        try:
                            await asyncio.gather(*all_tasks, return_exceptions=True)
                        except Exception as e:
                            print(f"[ERROR] Task execution error: {e}")
                        finally:
                            # Cancel main loop task when connection ends
                            main_loop_task.cancel()
                            try:
                                await main_loop_task
                            except asyncio.CancelledError:
                                pass
                                
            except asyncio.CancelledError:
                print("[INFO] Main loop cancelled.")
                break
            except (ConnectionRefusedError, ConnectionError, OSError) as e:
                print(f"[ERROR] Connection failed: {e}. Server may be down.")
                connection_failures += 1
                
                # Check if we should enter code mode after 2 connection failures
                if connection_failures >= 2 and not code_mode_active:
                    print(f"[INFO] {connection_failures} connection failures detected. Entering code mode...")
                    await self.display_manager.update_display("code")
                    print("[INFO] Code mode active - speech will be routed to Claude Code")
                    code_mode_active = True
                else:
                    await self.display_manager.update_display("error", text="Server Offline")
                
                if not code_mode_active:
                    print(f"[INFO] Retrying connection in 30 seconds...")
                    await asyncio.sleep(30)
                else:
                    print("[INFO] Code mode active - stopping connection attempts. Use voice commands or keyboard.")
                    await asyncio.sleep(5)  # Short sleep before trying again to see if user wants to exit code mode
            except Exception as e:
                print(f"[ERROR] Unhandled connection-level exception: {e}")
                traceback.print_exc()
                connection_failures += 1  # Also count general exceptions as connection failures
                
                # Check if we should enter code mode after 2 connection failures
                if connection_failures >= 2 and not code_mode_active:
                    print(f"[INFO] {connection_failures} connection failures detected. Entering code mode...")
                    await self.display_manager.update_display("code")
                    print("[INFO] Code mode active - speech will be routed to Claude Code")
                    code_mode_active = True
                else:
                    await self.display_manager.update_display("error", text="Connection Error")
                
                if not code_mode_active:
                    print(f"[INFO] Retrying connection in 30 seconds...")
                    await asyncio.sleep(30)
                else:
                    print("[INFO] Code mode active - stopping connection attempts. Use voice commands or keyboard.")
                    await asyncio.sleep(5)  # Short sleep before trying again to see if user wants to exit code mode
            finally:
                self.mcp_session = None
                if connection_attempts == 0:  # Only show disconnected state if we were previously connected
                    await self.display_manager.update_display("disconnected")
        
        # Cancel background tasks
        for task in background_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    
    async def sleep_timeout_monitor(self):
        """Background task to monitor for sleep timeout (5 minutes of inactivity)"""
        SLEEP_TIMEOUT = 300  # 5 minutes in seconds
        
        while True:
            try:
                current_state = self.display_manager.current_state
                
                # Only check for sleep timeout when in idle state
                if current_state == 'idle':
                    time_since_interaction = self.input_manager.get_time_since_last_interaction()
                    
                    if time_since_interaction >= SLEEP_TIMEOUT:
                        print(f"[INFO] Sleep timeout reached ({time_since_interaction:.1f}s since last interaction)")
                        await self.display_manager.update_display('sleep')
                    
                await asyncio.sleep(1)  # Check every second for precision
                
            except Exception as e:
                print(f"[ERROR] Sleep timeout monitor error: {e}")
                await asyncio.sleep(5)  # Wait longer on error
            
    async def cleanup(self):
        """Clean up resources"""
        print("[INFO] Starting client cleanup...")
        if self.audio_coordinator: 
            await self.audio_coordinator.cleanup()
        if self.audio_manager: 
            await self.audio_manager.cleanup()
        if self.display_manager: 
            self.display_manager.cleanup()
        if self.input_manager: 
            self.input_manager.cleanup()
        print("[INFO] Client cleanup finished.")
    
    async def route_to_claude_code(self, transcript: str):
        """Route speech transcript to Claude Code with health check and session management"""
        from claude.claude_code_healthcheck import execute_claude_code_with_health_check
        
        try:
            print(f"[INFO] Routing to Claude Code: '{transcript}'")
            
            # Update display to show processing
            await self.display_manager.update_display("thinking", mood="focused")
            
            # Process with Claude Code using health check and session management
            result = await execute_claude_code_with_health_check(transcript)
            
            if result["success"]:
                response = result.get("response", "")
                execution_time = result.get("execution_time", 0)
                session_info = result.get("session_info", "Unknown session")
                
                print(f"[INFO] Claude Code completed in {execution_time:.1f}s via {session_info}")
                print(f"[INFO] Response: {response[:100]}{'...' if len(response) > 100 else ''}")
                
                # Determine if we should speak the response
                should_speak = self._should_speak_claude_response(response, transcript)
                
                if should_speak and response:
                    # Speak the response via TTS
                    await self.display_manager.update_display("speaking", mood="helpful")
                    
                    # Use a shorter summary for very long responses
                    if len(response) > 300:
                        speech_text = "Task completed successfully. Check the output for details."
                    else:
                        speech_text = response
                        
                    try:
                        # Use the existing TTS system
                        audio_file = await self.tts_handler.synthesize_speech(
                            speech_text,
                            voice_id="default"
                        )
                        
                        if audio_file:
                            await self.audio_manager.play_audio(audio_file)
                    except Exception as tts_error:
                        print(f"[ERROR] TTS failed: {tts_error}")
                        # Fall back to success sound
                        await self.audio_manager.play_audio(
                            "/home/user/rp_client/assets/sounds/sound_effects/successfulloadup.mp3"
                        )
                else:
                    # Just confirm completion without speaking the full response
                    await self.audio_manager.play_audio(
                        "/home/user/rp_client/assets/sounds/sound_effects/successfulloadup.mp3"
                    )
                    
            else:
                # Handle error
                error = result.get("error", "Unknown error")
                print(f"[ERROR] Claude Code failed: {error}")
                
                # Speak error notification
                await self.display_manager.update_display("speaking", mood="confused")
                try:
                    error_text = f"Claude Code error: {error}"
                    audio_file = await self.tts_handler.synthesize_speech(
                        error_text[:200],  # Limit error message length
                        voice_id="default"
                    )
                    if audio_file:
                        await self.audio_manager.play_audio(audio_file)
                except:
                    # Fall back to error sound if TTS fails
                    pass
                    
        except Exception as e:
            print(f"[ERROR] Failed to route to Claude Code: {e}")
            # Handle error gracefully
            
        finally:
            # Update interaction time on successful completion
            self.input_manager.update_last_interaction()
            # Return to idle state
            await self.display_manager.update_display("idle", mood="casual")
    
    def _should_speak_claude_response(self, response: str, original_command: str) -> bool:
        """Determine if Claude Code response should be spoken"""
        if not response:
            return False
            
        # Don't speak very long responses
        if len(response) > 500:
            return False
            
        # Don't speak responses that look like code
        code_indicators = ['```', 'def ', 'class ', 'import ', 'function', '{', '}', 'const ', 'let ', 'var ']
        if any(indicator in response for indicator in code_indicators):
            return False
            
        # Don't speak file paths or technical output
        if response.startswith('/') or 'http://' in response or 'https://' in response:
            return False
            
        # Check for coding-related commands
        coding_keywords = ['create', 'write', 'implement', 'code', 'function', 'debug', 'fix', 'refactor']
        is_coding_command = any(keyword in original_command.lower() for keyword in coding_keywords)
        
        # For coding commands, be more conservative about speaking
        if is_coding_command and len(response) > 200:
            return False
            
        # Speak conversational responses
        return True
    
    async def inject_to_claude_code(self, transcript: str):
        """Inject transcript directly into Claude Code terminal using virtual keyboard"""
        await self.inject_to_claude_code_with_sounds(transcript, None)
    
    async def inject_to_claude_code_with_sounds(self, transcript: str, data_processing_task):
        """Inject transcript with phase-based sound transitions"""
        import subprocess
        import os
        
        try:
            print(f"[INFO] Injecting to Claude Code: '{transcript}'")
            
            # Path to our voice injector
            project_root = os.path.dirname(os.path.abspath(__file__))
            injector_script = os.path.join(project_root, "claude", "claude_voice_injector.py")
            venv_python = os.path.join(project_root, "venv", "bin", "python")
            
            # Processing phase: Copy transcript to clipboard
            try:
                # Use pyclip to put transcript in clipboard
                import pyclip
                pyclip.copy(transcript)
                print(f"[INFO] Transcript copied to clipboard")
            except Exception as e:
                print(f"[WARNING] Failed to copy to clipboard: {e}")
            
            # Teletype already playing from immediate feedback - no transition needed
            
            # Start teletype sound immediately before typing (MP3 has built-in 0.2s silence for sync)
            print("[INFO] Starting teletype sound with built-in timing...")
            asyncio.create_task(self._play_claude_code_confirmation())
            
            # Delay to ensure audio is playing before subprocess blocks
            await asyncio.sleep(0.45)
            
            # Run the voice injector with sudo to create virtual keyboard
            print("[INFO] Creating virtual keyboard for injection...")
            result = subprocess.run([
                'sudo', venv_python, injector_script, '--inject-text', transcript
            ], capture_output=True, text=True, timeout=30)
            
            # Stop teletype sound when injection completes
            print("[DEBUG] Injection complete, stopping typing phase sound...")
            await self.audio_coordinator.play_phase_sound("complete")
            
            if result.returncode == 0:
                print("[INFO] Successfully injected transcript to Claude Code")
            else:
                print(f"[ERROR] Injection failed: {result.stderr}")
                
        except Exception as e:
            print(f"[ERROR] Failed to inject to Claude Code: {e}")
            import traceback
            traceback.print_exc()
    
    async def send_enter_key(self):
        """Send Enter key using virtual keyboard for 'send now' wake word"""
        import subprocess
        import os
        
        try:
            print("[INFO] Sending Enter key to focused application")
            
            # Path to our Enter key sender
            project_root = os.path.dirname(os.path.abspath(__file__))
            enter_script = os.path.join(project_root, "claude", "send_enter.py")
            venv_python = os.path.join(project_root, "venv", "bin", "python")
            
            # Run the Enter key sender with sudo
            result = subprocess.run([
                'sudo', venv_python, enter_script
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print("[INFO] Successfully sent Enter key")
            else:
                print(f"[ERROR] Failed to send Enter key: {result.stderr}")
                
        except Exception as e:
            print(f"[ERROR] Failed to send Enter key: {e}")
            import traceback
            traceback.print_exc()
    
    def _should_route_to_claude_code_from_wake(self, wake_event_source: str) -> bool:
        """Check if wake event is for Claude Code (for confirmation sound)"""
        return self._should_route_to_claude_code(wake_event_source) or wake_event_source == "keyboard_code"
    
    async def _play_claude_code_confirmation(self):
        """Play teletype sound with built-in timing (MP3 has 0.2s silence at start)"""
        teletype = "/home/user/rp_client/assets/sounds/sound_effects/teletype.mp3"
        print("[DEBUG] Playing teletype sound with built-in sync timing!")
        if os.path.exists(teletype):
            try:
                await self.audio_coordinator.play_phase_sound("processing", teletype)
                print("[DEBUG] Teletype sound playback completed")
            except Exception as e:
                print(f"[DEBUG] Teletype playback failed: {e}")
                # Try direct fallback
                try:
                    await self.audio_coordinator.play_audio_file(teletype)
                    print("[DEBUG] Teletype fallback playback completed")
                except Exception as e2:
                    print(f"[DEBUG] Teletype fallback also failed: {e2}")
        else:
            print(f"[DEBUG] Teletype file not found: {teletype}")
    
    async def _delayed_teletype_sound(self, teletype_file):
        """Play teletype sound after 0.6s delay"""
        await asyncio.sleep(0.6)
        print("[DEBUG] Starting teletype sound after delay...")
        try:
            await self.audio_coordinator.play_phase_sound("processing", teletype_file)
            print("[DEBUG] Teletype sound playback completed")
        except Exception as e:
            print(f"[DEBUG] Teletype sound playback failed: {e}")
            # Try direct fallback
            try:
                await self.audio_coordinator.play_audio_file(teletype_file)
                print("[DEBUG] Teletype fallback playback completed")
            except Exception as e2:
                print(f"[DEBUG] Teletype fallback also failed: {e2}")
    
    def _switch_to_persona(self, persona: str):
        """
        Switch both display profile and TTS voice configuration
        
        Args:
            persona: 'laura' for LAURA persona, 'claude_code' for Claude Code persona
        """
        import json
        
        print(f"[INFO] Switching to {persona} persona")
        
        # Switch display profile
        if persona == 'laura':
            self.display_manager.set_display_profile('normal')
        elif persona == 'claude_code':
            self.display_manager.set_display_profile('claude_code')
        
        # Update TTS voice configuration
        try:
            # Update TTS server voices.json
            voices_config_path = "/home/user/rp_client/TTS/config/voices.json"
            with open(voices_config_path, 'r') as f:
                voices_config = json.load(f)
            
            if persona == 'laura':
                voices_config['active_voice'] = 'qEwI395unGwWV1dn3Y65'  # LAURA voice
            elif persona == 'claude_code':
                voices_config['active_voice'] = 'uY96J30mUhYUIymmD5cu'  # Claude Code voice
            
            with open(voices_config_path, 'w') as f:
                json.dump(voices_config, f, indent=2)
            
            # Notify TTS server to reload configuration
            import aiohttp
            import asyncio
            
            async def reload_tts_config():
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post('http://localhost:5000/reload_config') as response:
                            if response.status == 200:
                                print(f"[INFO] TTS server reloaded config for {persona} persona")
                            else:
                                print(f"[WARNING] TTS reload returned status {response.status}")
                except Exception as e:
                    print(f"[WARNING] Could not notify TTS server to reload: {e}")
            
            # Run the reload in the background
            asyncio.create_task(reload_tts_config())
            
            print(f"[INFO] Updated TTS voice to {persona} persona")
            
        except Exception as e:
            print(f"[ERROR] Failed to update TTS voice configuration: {e}")
    
    def _should_route_to_claude_code(self, wake_event_source: str) -> bool:
        """
        Determine if wake event should route to Claude Code CLI
        
        Args:
            wake_event_source: The wake event source (e.g., "wakeword (YourNewModel.pmdl)")
            
        Returns:
            bool: True if should route to Claude Code, False for regular chat
        """
        if not wake_event_source or 'wakeword' not in wake_event_source:
            return False
            
        # Extract model name from wake event source
        if '(' in wake_event_source and ')' in wake_event_source:
            model_name = wake_event_source.split('(')[1].rstrip(')')
            
            # Define wake words that should route to Claude Code
            claude_code_wake_words = [
                "claudecode.pmdl",
            ]
            
            return model_name in claude_code_wake_words
            
        return False
    
    def _should_send_enter_key(self, wake_event_source: str) -> bool:
        """
        Determine if wake event should send Enter key
        
        Args:
            wake_event_source: The wake event source (e.g., "wakeword (send_now.pmdl)")
            
        Returns:
            bool: True if should send Enter key, False otherwise
        """
        if not wake_event_source or 'wakeword' not in wake_event_source:
            return False
            
        # Extract model name from wake event source
        if '(' in wake_event_source and ')' in wake_event_source:
            model_name = wake_event_source.split('(')[1].rstrip(')')
            
            # Define wake words that should send Enter
            send_enter_wake_words = [
                "send_now.pmdl",
            ]
            
            return model_name in send_enter_wake_words
            
        return False
    
    def _should_send_note_to_mac(self, wake_event_source: str) -> bool:
        """
        Determine if wake event should trigger note transfer to Mac
        
        Args:
            wake_event_source: The wake event source (e.g., "wakeword (sendnote.pmdl)")
            
        Returns:
            bool: True if should send note to Mac, False otherwise
        """
        if not wake_event_source or 'wakeword' not in wake_event_source:
            return False
            
        # Extract model name from wake event source
        if '(' in wake_event_source and ')' in wake_event_source:
            model_name = wake_event_source.split('(')[1].rstrip(')')
            
            # Define wake words that should trigger note transfer
            note_transfer_wake_words = [
                "sendnote.pmdl",
            ]
            
            return model_name in note_transfer_wake_words
            
        return False
    
    async def send_note_to_mac(self):
        """Send pi500_note.txt to Mac server via MCP endpoint"""
        try:
            from send_note_to_mac import Pi500NoteSender
            
            sender = Pi500NoteSender()
            result = sender.send_note()
            
            if result["success"]:
                # Success - play confirmation sound and speak result
                success_sound = "/home/user/rp_client/assets/sounds/sound_effects/successfulloadup.mp3"
                if os.path.exists(success_sound):
                    await self.audio_coordinator.play_audio_file(success_sound)
                
                message = "Note successfully sent to Mac server!"
                print(f"[INFO] {message}")
                
                # Speak confirmation
                await self.tts_handler.speak_text(
                    message,
                    voice_params={"persona": "laura"},
                    coordinator=self.audio_coordinator
                )
                
            else:
                # Error - play error sound and speak error
                error_sound = "/home/user/rp_client/assets/sounds/sound_effects/error.mp3"
                if os.path.exists(error_sound):
                    await self.audio_coordinator.play_audio_file(error_sound)
                
                message = f"Failed to send note: {result.get('error', 'Unknown error')}"
                print(f"[ERROR] {message}")
                
                # Speak error
                await self.tts_handler.speak_text(
                    "Sorry, I couldn't send the note to Mac. Check the connection.",
                    voice_params={"persona": "laura"},
                    coordinator=self.audio_coordinator
                )
                
        except Exception as e:
            print(f"[ERROR] Exception in send_note_to_mac: {e}")
            
            # Play error sound
            error_sound = "/home/user/rp_client/assets/sounds/sound_effects/error.mp3"
            if os.path.exists(error_sound):
                await self.audio_coordinator.play_audio_file(error_sound)
            
            # Speak error
            await self.tts_handler.speak_text(
                "Sorry, there was an error sending the note.",
                voice_params={"persona": "laura"},
                coordinator=self.audio_coordinator
            )


async def main():
    """Main entry point with multi-task architecture"""
    from config.client_config import load_client_settings
    load_client_settings()
    
    # GameBoy-style mode: No local speech processing, using Apple Watch input
    print("[INFO] GameBoy-style mode: Speech input via Apple Watch voice injection")
    print("[INFO] Local speech processing disabled - Apple Watch provides transcribed text")
    
    client = PiMCPClient(server_url=SERVER_URL, device_id=DEVICE_ID)
    
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\n[INFO] KeyboardInterrupt received.")
    finally:
        print("[INFO] Main function finished. Performing final cleanup...")
        await client.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Application terminated by user.")
    finally:
        print("[INFO] Application shutdown complete.")
