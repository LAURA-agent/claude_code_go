#!/usr/bin/env python3
"""
VOSK WebSocket Client
Replacement for direct VoskTranscriber that connects to shared VOSK server
"""

import asyncio
import websockets
import json
import logging
import time
import threading
import queue
from typing import Optional, Tuple

logger = logging.getLogger('vosk_client')


class VoskWebSocketClient:
    """
    Drop-in replacement for VoskTranscriber that uses WebSocket server
    Maintains the same interface as the original VoskTranscriber
    """
    
    def __init__(self, server_url: str = "ws://localhost:2700", sample_rate: int = 16000):
        self.server_url = server_url
        self.sample_rate = sample_rate
        self.websocket = None
        self.session_id = None
        self.connected = False
        
        # Response handling
        self.response_queue = queue.Queue()
        self.partial_text = ""
        self.complete_text = ""
        
        
        # Event loop for async operations
        self.loop = None
        self.loop_thread = None
        self.connect_event = threading.Event()
        
        # Start background event loop
        self._start_background_loop()
        
    def _start_background_loop(self):
        """Start background event loop for WebSocket operations"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
            
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        
        # Wait for loop to be ready
        time.sleep(0.1)
        
    async def _connect(self):
        """Connect to VOSK WebSocket server"""
        try:
            self.websocket = await websockets.connect(
                self.server_url,
                max_size=10**7,  # 10MB max message size
                ping_interval=20,
                ping_timeout=10
            )
            
            # Wait for connection confirmation
            response = await self.websocket.recv()
            data = json.loads(response)
            
            if data.get('type') == 'connection' and data.get('status') == 'connected':
                self.session_id = data.get('session_id')
                self.connected = True
                logger.info(f"Connected to VOSK server: {self.session_id}")
                
                # Start message handler
                asyncio.create_task(self._message_handler())
                
                return True
            else:
                logger.error(f"Unexpected connection response: {data}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to VOSK server: {e}")
            self.connected = False
            return False
            
    async def _message_handler(self):
        """Handle incoming messages from server"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                self.response_queue.put(data)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"Message handler error: {e}")
            self.connected = False
            
    def connect(self) -> bool:
        """Connect to VOSK server (synchronous)"""
        if not self.loop:
            print(f"[VOSK DEBUG] No event loop available!")
            return False
        
        if not self.loop.is_running():
            print(f"[VOSK DEBUG] Event loop is not running!")
            return False
            
        print(f"[VOSK DEBUG] Attempting WebSocket connection to {self.server_url}")
        future = asyncio.run_coroutine_threadsafe(self._connect(), self.loop)
        try:
            result = future.result(timeout=10.0)
            print(f"[VOSK DEBUG] Connection result: {result}")
            return result
        except Exception as e:
            print(f"[VOSK DEBUG] Connection failed with exception: {e}")
            logger.error(f"Connection timeout: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from server"""
        if self.websocket and self.connected:
            future = asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)
            try:
                future.result(timeout=5.0)
            except:
                pass
            self.connected = False
            
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
            
    def reset(self):
        """Reset transcriber state for new utterance"""
        # Clear both text states for new utterance - like native VOSK reset()
        self.complete_text = ""
        self.partial_text = ""
        
        if not self.connected:
            print(f"[VOSK DEBUG] Not connected, attempting to connect to {self.server_url}")
            if not self.connect():
                print(f"[VOSK DEBUG] Connection failed!")
                raise RuntimeError("Failed to connect to VOSK server")
            else:
                print(f"[VOSK DEBUG] Connection successful!")
                
        # Send reset command
        command = {'type': 'reset'}
        future = asyncio.run_coroutine_threadsafe(
            self.websocket.send(json.dumps(command)), 
            self.loop
        )
        try:
            future.result(timeout=5.0)
        except Exception as e:
            logger.error(f"Reset command failed: {e}")
            
        # Clear response queue
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break
                
    def process_frame(self, frame_data_bytes: bytes) -> Tuple[bool, bool, str]:
        """
        Process audio frame and return transcription results
        
        Returns:
            Tuple of (is_final_chunk_result, is_speech_in_frame, current_full_text)
        """
        if not self.connected:
            print(f"[VOSK DEBUG] Not connected, attempting to connect to {self.server_url}")
            if not self.connect():
                print(f"[VOSK DEBUG] Connection failed during process_frame!")
                return False, False, ""
            print(f"[VOSK DEBUG] Connected successfully during process_frame")
            
        # Send audio data
        # Debug: Track frame sending
        if not hasattr(self, 'frame_count'):
            self.frame_count = 0
        self.frame_count += 1
        
        # Log every 50th frame (about once per second at 16kHz with 320 sample frames)
        if self.frame_count % 50 == 0:
            print(f"[VOSK DEBUG] Sending frame {self.frame_count}, size: {len(frame_data_bytes)} bytes")
        
        future = asyncio.run_coroutine_threadsafe(
            self.websocket.send(frame_data_bytes), 
            self.loop
        )
        try:
            future.result(timeout=1.0)
        except Exception as e:
            logger.error(f"Failed to send audio frame: {e}")
            print(f"[VOSK DEBUG] Failed to send frame {self.frame_count}: {e}")
            self.connected = False  # Mark as disconnected
            # Try to reconnect on next reset()
            return False, False, ""
            
        # Check for immediate responses (non-blocking)
        try:
            response = self.response_queue.get(timeout=0.1)
            # Only log finals, not every response
            if response.get('type') == 'final':
                print(f"[VOSK DEBUG] Received final: {response}")
            return self._process_response(response)
        except queue.Empty:
            # Don't log empty queue - this is normal
            return False, False, self._get_current_text()
            
    def _process_response(self, response: dict) -> Tuple[bool, bool, str]:
        """Process a response from the server - mirrors native VOSK behavior exactly"""
        response_type = response.get('type')
        
        if response_type == 'final':
            # EXACTLY like native VOSK line 50: accumulate finals into complete_text
            text = response.get('text', '').strip()
            if text:
                self.complete_text = (self.complete_text + " " + text).strip() if self.complete_text else text
                return True, True, self._get_current_combined_text()
            else:
                return True, False, self._get_current_combined_text()
                
        elif response_type == 'partial':
            # EXACTLY like native VOSK line 57: store current partial
            self.partial_text = response.get('text', '').strip()
            is_speech = bool(self.partial_text)
            return False, is_speech, self._get_current_combined_text()
            
        elif response_type == 'error':
            logger.error(f"Server error: {response.get('message')}")
            
        return False, False, self._get_current_combined_text()
        
    def _get_current_combined_text(self) -> str:
        """
        Get current combined text with intelligent deduplication
        
        DEDUPLICATION LOGIC:
        - If partial_text contains complete_text, use partial_text (more recent)
        - If complete_text contains partial_text, use complete_text (more complete)
        - If they're different, concatenate them
        - If one is empty, use the other
        """
        if not self.complete_text:
            return self.partial_text
        if not self.partial_text:
            return self.complete_text
            
        # Check for content overlap to prevent duplication
        complete_clean = self.complete_text.strip()
        partial_clean = self.partial_text.strip()
        
        # If partial contains complete (partial is more recent/complete)
        if complete_clean in partial_clean:
            return partial_clean
        # If complete contains partial (complete is more comprehensive)
        elif partial_clean in complete_clean:
            return complete_clean
        # If they're identical
        elif complete_clean == partial_clean:
            return complete_clean
        # If they're different, concatenate (original behavior)
        else:
            return (complete_clean + " " + partial_clean).strip()
        
    def _get_current_text(self) -> str:
        """Backward compatibility alias"""
        return self._get_current_combined_text()
            
    def get_final_text(self) -> str:
        """
        Get final transcription result when VAD determines speech has ended
        
        CRITICAL DESIGN PRINCIPLE:
        - VAD controls timing (when to start/stop transcription)
        - VOSK server provides the most complete transcription via FinalResult()
        - Client accumulates partials as fallback for fragmented sessions
        
        VOSK SERVER FINAL_RESULT vs CLIENT STATE:
        - Server calls recognizer.FinalResult() which consolidates entire session
        - Client state (complete_text + partial_text) may be fragmented due to timing conflicts
        - Server result is more authoritative for continuous speech
        """
        print(f"[VOSK DEBUG] get_final_text called. complete_text: '{self.complete_text}', partial_text: '{self.partial_text}'")
        
        # REQUEST COMPLETE TRANSCRIPTION from server
        # Server calls VOSK's native FinalResult() which processes all accumulated audio
        if self.connected:
            # Give VOSK a moment to finish processing any remaining audio frames
            import time
            time.sleep(0.1)
            command = {'type': 'final'}
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.websocket.send(json.dumps(command)), 
                    self.loop
                )
                future.result(timeout=1.0)
                print(f"[VOSK DEBUG] Sent final command to server")
                
                # CAPTURE SERVER'S FINAL_RESULT (most complete transcription)
                server_final_result = None
                for _ in range(5):  # Try up to 5 times to get responses
                    try:
                        response = self.response_queue.get(timeout=0.2)
                        print(f"[VOSK DEBUG] Got response: {response}")
                        self._process_response(response)
                        
                        # Server's final_result contains complete session transcription
                        if response.get('type') == 'final_result':
                            server_final_result = response.get('text', '').strip()
                            print(f"[VOSK DEBUG] Server provided complete final: '{server_final_result}'")
                            
                    except queue.Empty:
                        break
                        
            except Exception as e:
                print(f"[VOSK DEBUG] Error requesting final: {e}")
        
        # TRANSCRIPT PRIORITY: Server final > Client combined > Empty
        # Server result is most authoritative because it calls VOSK's FinalResult()
        if server_final_result:
            final_result = server_final_result
            print(f"[VOSK DEBUG] Using server final result: '{final_result}'")
        else:
            # FALLBACK: Use client's accumulated state (complete + partial)
            final_result = self._get_current_combined_text().strip()
            print(f"[VOSK DEBUG] Using client combined result: '{final_result}'")
        
        # CLEANUP: Reset state for next transcription session
        self.partial_text = ""
        self.complete_text = ""
        
        return final_result
        
    def cleanup(self):
        """Clean up resources"""
        self.disconnect()
        
    def __del__(self):
        """Destructor"""
        try:
            self.cleanup()
        except:
            pass


# Convenience function for drop-in replacement
def VoskTranscriber(model_path: str = None, sample_rate: int = 16000, server_url: str = "ws://localhost:2700"):
    """
    Drop-in replacement for original VoskTranscriber
    Ignores model_path and uses WebSocket server instead
    """
    return VoskWebSocketClient(server_url=server_url, sample_rate=sample_rate)