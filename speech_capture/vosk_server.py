#!/usr/bin/env python3
"""
Shared VOSK WebSocket Server
Provides centralized speech-to-text service for multiple clients
"""

import asyncio
import websockets
import json
import logging
import os
import sys
from pathlib import Path
from vosk import Model, KaldiRecognizer
import threading
import queue
import time

# Setup logging with filtered websockets errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('vosk_server')

# Suppress harmless websocket handshake failures
class WebSocketErrorFilter(logging.Filter):
    def filter(self, record):
        # Suppress common harmless errors
        if record.name == 'websockets.server':
            message = record.getMessage()
            # Filter out port scanner and invalid handshake attempts
            if any(phrase in message for phrase in [
                'opening handshake failed',
                'did not receive a valid HTTP request',
                'connection closed while reading HTTP request'
            ]):
                return False
        return True

# Apply filter to websockets logger
websockets_logger = logging.getLogger('websockets.server')
websockets_logger.addFilter(WebSocketErrorFilter())

# Import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.client_config import VOSK_MODEL_PATH, AUDIO_SAMPLE_RATE


class VoskServer:
    def __init__(self, model_path: str, sample_rate: int = 16000, port: int = 2700):
        self.model_path = model_path
        self.sample_rate = sample_rate
        self.port = port
        self.model = None
        self.active_sessions = {}
        self.server = None
        
        # Server stats
        self.start_time = time.time()
        self.total_sessions = 0
        self.active_session_count = 0
        
    async def initialize_model(self):
        """Initialize VOSK model in a thread to avoid blocking"""
        def load_model():
            logger.info(f"Loading VOSK model from {self.model_path}")
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"VOSK model not found at: {self.model_path}")
            self.model = Model(self.model_path)
            logger.info("VOSK model loaded successfully")
            
        # Load model in thread to prevent blocking
        await asyncio.get_event_loop().run_in_executor(None, load_model)
        
        # Launch LAURA client after model is ready
        # DISABLED: No longer auto-launching LAURA to prevent conflicts
        logger.info("VOSK model loaded - ready for WebSocket connections")
        
    async def _launch_laura_client(self):
        """Launch LAURA client system after VOSK model is ready"""
        import subprocess
        import os
        
        # DISABLED: Auto-launch LAURA to prevent conflicts with manual LAURA instances
        # When using desktop icon, user should manually start LAURA separately
        logger.info("VOSK server starting - LAURA auto-launch disabled to prevent conflicts")
        
    def create_recognizer(self, session_id: str) -> KaldiRecognizer:
        """Create a new recognizer for a session"""
        recognizer = KaldiRecognizer(self.model, self.sample_rate)
        recognizer.SetWords(True)
        return recognizer
        
    async def handle_client(self, websocket):
        """Handle a WebSocket client connection"""
        session_id = f"session_{time.time()}_{id(websocket)}"
        client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
        
        logger.info(f"New client connected: {session_id} from {client_ip}")
        
        try:
            # Create recognizer for this session
            recognizer = self.create_recognizer(session_id)
            self.active_sessions[session_id] = {
                'recognizer': recognizer,
                'websocket': websocket,
                'client_ip': client_ip,
                'start_time': time.time(),
                'frames_processed': 0
            }
            self.active_session_count += 1
            self.total_sessions += 1
            
            # Send initial connection confirmation
            await websocket.send(json.dumps({
                'type': 'connection',
                'status': 'connected',
                'session_id': session_id,
                'sample_rate': self.sample_rate
            }))
            
            async for message in websocket:
                try:
                    if isinstance(message, bytes):
                        # Audio data
                        await self.process_audio_frame(session_id, message)
                    else:
                        # JSON commands
                        await self.handle_command(session_id, json.loads(message))
                        
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': 'Invalid JSON command'
                    }))
                except Exception as e:
                    logger.error(f"Error processing message from {session_id}: {e}")
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': str(e)
                    }))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {session_id} disconnected normally")
        except Exception as e:
            logger.error(f"Error handling client {session_id}: {e}")
        finally:
            # Cleanup session
            if session_id in self.active_sessions:
                session_info = self.active_sessions[session_id]
                duration = time.time() - session_info['start_time']
                frames = session_info['frames_processed']
                logger.info(f"Session {session_id} ended: {duration:.1f}s, {frames} frames")
                del self.active_sessions[session_id]
                self.active_session_count -= 1
                
    async def process_audio_frame(self, session_id: str, audio_data: bytes):
        """Process an audio frame for transcription"""
        if session_id not in self.active_sessions:
            return
            
        session = self.active_sessions[session_id]
        recognizer = session['recognizer']
        websocket = session['websocket']
        session['frames_processed'] += 1
        
        # Debug: Log frame info every 100 frames
        if session['frames_processed'] % 100 == 0:
            logger.info(f"Session {session_id}: Processed {session['frames_processed']} frames, current frame: {len(audio_data)} bytes")
        
        try:
            if recognizer.AcceptWaveform(audio_data):
                # VOSK internal final - DO NOT USE Result() as it corrupts FinalResult()
                # Just acknowledge the internal final but don't process it
                logger.info(f"VOSK internal final triggered for {session_id} - ignoring to preserve FinalResult() state")
                
                # Send a minimal acknowledgment without calling Result()
                response = {
                    'type': 'final',
                    'text': '',  # Don't provide text from corrupted Result()
                    'confidence': 0.0,
                    'session_id': session_id
                }
                
                await websocket.send(json.dumps(response))
                
            else:
                # Partial result
                partial_result = json.loads(recognizer.PartialResult())
                partial_text = partial_result.get("partial", "").strip()
                
                if partial_text and session['frames_processed'] % 50 == 0:  # Log every 50 frames when there's partial text
                    logger.info(f"VOSK Partial result for {session_id}: '{partial_text}'")
                
                if partial_text:
                    response = {
                        'type': 'partial',
                        'text': partial_text,
                        'session_id': session_id
                    }
                    await websocket.send(json.dumps(response))
                    
        except Exception as e:
            logger.error(f"Error processing audio for {session_id}: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'Audio processing error: {str(e)}'
            }))
            
    async def handle_command(self, session_id: str, command: dict):
        """Handle JSON commands from clients"""
        if session_id not in self.active_sessions:
            return
            
        websocket = self.active_sessions[session_id]['websocket']
        cmd_type = command.get('type')
        
        if cmd_type == 'reset':
            # Reset recognizer for new utterance
            recognizer = self.create_recognizer(session_id)
            self.active_sessions[session_id]['recognizer'] = recognizer
            
            await websocket.send(json.dumps({
                'type': 'reset_confirm',
                'session_id': session_id
            }))
            
        elif cmd_type == 'final':
            # Get final result
            recognizer = self.active_sessions[session_id]['recognizer']
            final_result = json.loads(recognizer.FinalResult())
            text = final_result.get("text", "").strip()
            
            await websocket.send(json.dumps({
                'type': 'final_result',
                'text': text,
                'confidence': final_result.get('confidence', 0.0),
                'session_id': session_id
            }))
            
        elif cmd_type == 'status':
            # Server status
            uptime = time.time() - self.start_time
            await websocket.send(json.dumps({
                'type': 'status',
                'server_uptime': uptime,
                'active_sessions': self.active_session_count,
                'total_sessions': self.total_sessions,
                'model_path': str(self.model_path),
                'sample_rate': self.sample_rate
            }))
            
        else:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'Unknown command type: {cmd_type}'
            }))
            
    async def start_server(self):
        """Start the WebSocket server"""
        # Initialize VOSK model first
        await self.initialize_model()
        
        # Start WebSocket server
        logger.info(f"Starting VOSK WebSocket server on port {self.port}")
        self.server = await websockets.serve(
            self.handle_client,
            "localhost",
            self.port,
            max_size=10**7,  # 10MB max message size for audio
            ping_interval=20,
            ping_timeout=10
        )
        
        logger.info(f"VOSK Server ready! Connect to ws://localhost:{self.port}")
        logger.info(f"Model: {self.model_path}")
        logger.info(f"Sample Rate: {self.sample_rate} Hz")
        
        # Keep server running
        await self.server.wait_closed()
        
    def stop_server(self):
        """Stop the WebSocket server"""
        if self.server:
            self.server.close()
            logger.info("VOSK Server stopped")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Shared VOSK WebSocket Server")
    parser.add_argument('--port', type=int, default=2700, help='WebSocket port (default: 2700)')
    parser.add_argument('--model', type=str, help='VOSK model path (default: from client_config)')
    parser.add_argument('--sample-rate', type=int, default=AUDIO_SAMPLE_RATE, help='Audio sample rate')
    
    args = parser.parse_args()
    
    # Use provided model path or default from config
    model_path = args.model or str(VOSK_MODEL_PATH)
    
    server = VoskServer(
        model_path=model_path,
        sample_rate=args.sample_rate,
        port=args.port
    )
    
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        server.stop_server()
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    # Make script executable
    import stat
    script_path = Path(__file__)
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
    
    # Run server
    asyncio.run(main())