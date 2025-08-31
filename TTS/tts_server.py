# tts_server.py
#!/usr/bin/env python3

import asyncio
import sys 
import os
import time
import traceback
import logging
import json
import glob
from pathlib import Path

# Configure logging for the server
logging.basicConfig(
    level=logging.INFO, # Can be DEBUG for more verbosity
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/tts_server.log", mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Suppress verbose logs from Quart framework
logging.getLogger('quart.app').setLevel(logging.WARNING)
logging.getLogger('quart.serving').setLevel(logging.WARNING)

from quart import Quart, request, jsonify
from quart_cors import cors
from audio_manager import AudioManager
from smart_streaming_processor import SimplifiedTTSProcessor # Updated import

CONFIG = {
    "output_dir": str(Path.home() / "LAURA" / "audio_cache"), # Example, ensure this path is valid
    "max_retries": 3,
    "retry_delay": 0.5,
    "notifications_dir": "/home/user/rp_client/tts_notifications"
}

os.makedirs(CONFIG["output_dir"], exist_ok=True)

app = Quart(__name__)
app = cors(app, allow_origin="*") # Allow all origins for browser extension

audio_manager = None
tts_processor = None # Renamed from streaming_handler

# Deduplication tracking
recent_messages = {}
MESSAGE_DEDUP_WINDOW = 2.0  # seconds to consider messages as duplicates

@app.before_serving
async def startup():
    global audio_manager, tts_processor
    logger.info("Server startup: Initializing audio manager...")
    
    # Clear stale notification files on startup to avoid processing old messages
    try:
        notifications_dir = Path(CONFIG["notifications_dir"])
        if notifications_dir.exists():
            stale_files = list(notifications_dir.glob("claude-*.json"))
            if stale_files:
                logger.info(f"Clearing {len(stale_files)} stale notification files on startup...")
                for stale_file in stale_files:
                    try:
                        stale_file.unlink()
                    except Exception as e:
                        logger.warning(f"Could not delete stale file {stale_file}: {e}")
                logger.info("Stale notifications cleared")
    except Exception as e:
        logger.warning(f"Error clearing stale notifications: {e}")
    
    try:
        audio_manager = AudioManager()
        if hasattr(audio_manager, 'initialize_input') and asyncio.iscoroutinefunction(audio_manager.initialize_input):
            await audio_manager.initialize_input()
        elif hasattr(audio_manager, 'initialize_input'):
            audio_manager.initialize_input() # Synchronous call if not async
            
        if audio_manager.is_initialized():
            logger.info("Audio manager initialized successfully.")
            tts_processor = SimplifiedTTSProcessor(audio_manager) # Use the new simplified processor
            logger.info("SimplifiedTTSProcessor initialized.")
            
        else:
            logger.error("Audio manager failed to initialize properly. TTS functionality will be impaired.")
            # tts_processor will remain None if audio_manager fails
            
    except Exception as e:
        logger.error(f"Fatal error during audio manager startup: {e}", exc_info=True)
        audio_manager = None 
        tts_processor = None

@app.route('/stream', methods=['POST'])
async def stream_text():
    global tts_processor
    if not tts_processor:
        logger.error("TTS Processor not available for /stream request.")
        return jsonify({"success": False, "error": "TTS Processor not initialized"}), 500

    try:
        data = await request.get_json()
        text = data.get('text', '')
        is_complete = data.get('is_complete', False)
        response_id = data.get('response_id', f'stream-{int(time.time())}')
        source = data.get('source', 'claude')  # NEW: Track where this came from

        # Log differently based on source
        if source == 'gemini':
            logger.info(f"🎭 Received ArgoVox chunk for [{response_id}]: {len(text)} chars, complete: {is_complete}")
        else:
            logger.info(f"📥 Received Claude chunk for [{response_id}]: {len(text)} chars, complete: {is_complete}")
        
        # Process the chunk normally - your existing processor handles everything
        await tts_processor.process_chunk(
            text_content=text,
            full_response_id=response_id,
            is_complete=is_complete
        )
        
        # If this chunk is marked as complete, wait for audio processing
        if is_complete and audio_manager:
            logger.info(f"Final chunk for {response_id}. Waiting for audio queue to process...")
            await audio_manager.wait_for_queue_empty(timeout=30.0) 
            await audio_manager.wait_for_audio_completion(timeout=5.0)
            logger.info(f"Audio completion wait finished for {response_id}.")

        return jsonify({
            "success": True,
            "processed": True,
            "response_id": response_id,
            "source": source  # Echo back so client knows we got it
        })

    except asyncio.TimeoutError:
        logger.warning(f"Timeout waiting for audio completion for final chunk {response_id}")
        return jsonify({"success": True, "message": "Processing initiated, audio completion timed out", "response_id": response_id}), 202
    except Exception as e:
        logger.error(f"❌ Stream error for {response_id}: {e}", exc_info=True)
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/stop_audio', methods=['POST'])
async def stop_audio():
    if audio_manager:
        try:
            logger.info("Received /stop_audio request")
            await audio_manager.stop_current_audio()
            # Optionally, also clear the queue if stop means discard pending
            await audio_manager.clear_queue() 
            logger.info("Audio stopped and queue cleared successfully via /stop_audio.")
            return jsonify({"success": True, "message": "Audio stopped and queue cleared"})
        except Exception as e:
            logger.error(f"Error stopping audio: {e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500
    else:
        logger.warning("Audio manager not available for /stop_audio")
        return jsonify({"success": False, "error": "Audio manager not available"}), 500

@app.route('/reload_config', methods=['POST'])
async def reload_config():
    """Reload voice configuration from disk"""
    try:
        from config.tts_config import VOICES_FILE
        import importlib
        from config import tts_config
        
        # Reload the tts_config module
        importlib.reload(tts_config)
        
        logger.info("🔄 Voice configuration reloaded from disk")
        return jsonify({"success": True, "message": "Configuration reloaded"})
    except Exception as e:
        logger.error(f"Error reloading config: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/reset_conversation', methods=['POST'])
async def reset_conversation():
    global tts_processor
    try:
        data = await request.get_json()
        response_id_context = data.get('response_id', f'reset-{int(time.time())}')
        
        logger.info(f"🔄 Reset conversation requested (context: {response_id_context})")
        
        if tts_processor:
            await tts_processor.reset_conversation(response_id_context)
        elif audio_manager: # Fallback if processor somehow not init but audio_manager is
             await audio_manager.clear_queue()
             await audio_manager.stop_current_audio()
             logger.info("Audio queue cleared and audio stopped during reset (processor not available).")
        else:
            logger.warning("Neither TTS processor nor audio manager available for reset.")


        return jsonify({
            "success": True, 
            "response_id": response_id_context,
            "message": f"Conversation reset successfully (context: {response_id_context})"
        })
    except Exception as e:
        logger.error(f"❌ Reset error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/tts', methods=['POST'])
async def text_to_speech_manual():
    global tts_processor, recent_messages
    if not tts_processor:
        logger.error("TTS Processor not available for /tts (manual) request.")
        return jsonify({"success": False, "error": "TTS Processor not initialized"}), 500

    try:
        data = await request.get_json()
        text = data.get('text', '')
        response_id = data.get('response_id', f'manual-{int(time.time())}')
        
        if not text.strip():
            logger.warning(f"Empty text provided for manual TTS {response_id}, skipping.")
            return jsonify({"error": "No text provided"}), 400

        # Deduplication check
        current_time = time.time()
        text_hash = hash(text.strip())
        
        # Clean old entries
        recent_messages = {k: v for k, v in recent_messages.items() 
                         if current_time - v < MESSAGE_DEDUP_WINDOW}
        
        # Check for duplicate
        if text_hash in recent_messages:
            logger.warning(f"🔁 Duplicate TTS request detected, ignoring: '{text[:50]}...'")
            return jsonify({"success": True, "message": "Duplicate message ignored"}), 200
        
        # Record this message
        recent_messages[text_hash] = current_time
        
        logger.info(f"📤 Manual TTS [{response_id}]: {len(text)} chars")
        
        # Get the current audio file before processing
        current_audio_file = None
        if audio_manager and hasattr(audio_manager, 'state') and hasattr(audio_manager.state, 'current_audio_file'):
            current_audio_file = audio_manager.state.current_audio_file
        
        await tts_processor.process_chunk(
            text_content=text,
            full_response_id=response_id,
            is_complete=True # Manual TTS is always a complete, single unit
        )
        
        # Capture the generated audio file path
        generated_audio_file = None
        if audio_manager:
            logger.info(f"Manual TTS {response_id}. Waiting for audio completion (timeout 30s).")
            await audio_manager.wait_for_audio_completion(timeout=30.0)
            
            # Try to get the audio file that was just processed
            if hasattr(audio_manager, 'state') and hasattr(audio_manager.state, 'current_audio_file'):
                generated_audio_file = audio_manager.state.current_audio_file
            
            logger.info(f"Audio completion wait finished for manual TTS {response_id}.")

        return jsonify({
            "success": True, 
            "processed": True,
            "response_id": response_id,
            "message": "Manual TTS processed",
            "audio_file": generated_audio_file  # Include the audio file path
        })

    except asyncio.TimeoutError:
        logger.warning(f"Timeout waiting for audio completion for manual TTS {response_id}")
        return jsonify({"success": True, "message": "Manual TTS initiated, audio completion timed out", "response_id": response_id}), 202
    except Exception as e:
        logger.error(f"❌ Manual TTS ERROR for {response_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/health', methods=['GET'])
async def health_check():
    audio_manager_status = "not initialized"
    if audio_manager:
        audio_manager_status = "ready" if audio_manager.is_initialized() else "initialization_failed_or_pending"
        
    return jsonify({
        "status": "ok",
        "server": "Claude-to-Speech TTS Server",
        "version": "2.5.0-simplified", # Version update
        "audio_manager": audio_manager_status,
        "tts_processor": "SimplifiedTTSProcessor" if tts_processor else "not_initialized",
        "features": {
            "one_shot_mode": "client_driven",
            "delta_processing": "client_driven",
            "server_text_cleaning": True,
            "zone_filtering": "client_driven (server trusts client chunks)"
        },
        "timestamp": time.time()
    })

@app.route('/')
async def home():
    return "Claude-to-Speech TTS Server (Simplified Processor) is running!"

@app.route('/claude_notifications', methods=['POST'])
async def process_claude_notifications():
    """
    Process Claude TTS notifications from JSON files.
    Claude writes JSON files when it needs to ask questions or draw attention.
    """
    global tts_processor
    if not tts_processor:
        logger.error("TTS Processor not available for Claude notifications.")
        return jsonify({"success": False, "error": "TTS Processor not initialized"}), 500

    try:
        notifications_dir = Path(CONFIG["notifications_dir"])
        if not notifications_dir.exists():
            return jsonify({"success": True, "message": "No notifications directory found", "processed": 0})

        # Find all unprocessed notification files, sorted by creation time
        notification_files = sorted(notifications_dir.glob("claude-*.json"), key=lambda x: x.stat().st_mtime)
        processed_count = 0

        for notification_file in notification_files:
            try:
                with open(notification_file, 'r') as f:
                    notification_data = json.load(f)
                
                # Skip if already processed
                if notification_data.get("already_ttsd", False):
                    notification_file.unlink()  # Clean up processed file
                    continue
                
                text = notification_data.get("text", "")
                message_id = notification_data.get("message_id", f"notification-{int(time.time())}")
                notification_type = notification_data.get("type", "status")
                priority = notification_data.get("priority", "medium")
                
                if text.strip():
                    # Just use the text directly without type prefixes
                    tts_text = text
                    
                    logger.info(f"🔔 Processing Claude {notification_type}: {message_id}")
                    
                    # Process through TTS
                    await tts_processor.process_chunk(
                        text_content=tts_text,
                        full_response_id=message_id,
                        is_complete=True
                    )
                    
                    # Mark as processed by deleting the file
                    notification_file.unlink()
                    processed_count += 1
                    logger.info(f"✅ Processed and deleted notification: {message_id}")
                    
            except Exception as e:
                logger.error(f"Error processing notification file {notification_file}: {e}")
                continue

        return jsonify({
            "success": True,
            "processed": processed_count,
            "message": f"Processed {processed_count} Claude notifications"
        })

    except Exception as e:
        logger.error(f"Error in Claude notifications processing: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/play_phase_sound', methods=['POST'])
async def play_phase_sound():
    """Play or stop sounds based on workflow phase"""
    try:
        data = await request.json
        phase = data.get('phase', '')
        sound_file = data.get('sound_file', None)
        
        # Stop current audio if any
        if audio_manager:
            logger.info(f"Stopping current audio for phase transition to: {phase}")
            try:
                # Use the correct method to stop audio
                await audio_manager.stop_current_audio()
                # Also stop pygame music directly to be sure
                if hasattr(audio_manager, 'mixer') and audio_manager.mixer:
                    audio_manager.mixer.music.stop()
            except Exception as e:
                logger.warning(f"Could not stop audio: {e}")
            await asyncio.sleep(0.1)  # Brief pause for audio cleanup
        
        # Start new phase sound if provided
        if sound_file and os.path.exists(sound_file):
            logger.info(f"Playing phase sound for {phase}: {sound_file}")
            # Start playing in background - don't await!
            asyncio.create_task(audio_manager.play_audio(sound_file))
            return jsonify({"status": "playing", "phase": phase, "file": sound_file}), 200
        else:
            logger.info(f"No sound for phase: {phase}")
            return jsonify({"status": "stopped", "phase": phase}), 200
            
    except Exception as e:
        logger.error(f"Error in play_phase_sound: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/reset_audio', methods=['POST']) # For full audio system re-init
async def reset_audio_system():
    global audio_manager, tts_processor
    logger.info("Received /reset_audio request. Attempting to reinitialize audio system.")
    try:
        if audio_manager:
            if hasattr(audio_manager, 'shutdown') and asyncio.iscoroutinefunction(audio_manager.shutdown):
                await audio_manager.shutdown()
            # No explicit else for non-async shutdown, assuming __del__ or manual stop handles it
        
        # Reinitialize audio_manager and tts_processor
        audio_manager = AudioManager() # This might re-run pygame.mixer.init()
        if hasattr(audio_manager, 'initialize_input') and asyncio.iscoroutinefunction(audio_manager.initialize_input):
            await audio_manager.initialize_input()
        elif hasattr(audio_manager, 'initialize_input'):
             audio_manager.initialize_input()


        if audio_manager.is_initialized():
            tts_processor = SimplifiedTTSProcessor(audio_manager)
            logger.info("Audio system and SimplifiedTTSProcessor reinitialized successfully.")
            return jsonify({"success": True, "message": "Audio system reinitialized successfully."})
        else:
            logger.error("Audio system reinitialization failed.")
            tts_processor = None
            return jsonify({"success": False, "error": "Audio system reinitialization failed."}), 500
            
    except Exception as e:
        logger.error(f"Error during audio system reset: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/audio_status', methods=['GET'])
async def get_audio_status():
    """
    Get current audio playback status for TTS coordination.
    Used by ClaudeTTSCoordinator to monitor TTS completion.
    """
    global audio_manager
    
    try:
        if not audio_manager:
            return jsonify({
                "success": True,
                "is_speaking": False,
                "audio_manager": "not_initialized",
                "queue_size": 0
            })
            
        # Check if audio manager is currently playing
        is_speaking = getattr(audio_manager, 'is_speaking', False)
        
        # Check queue size if available
        queue_size = 0
        if hasattr(audio_manager, 'audio_queue'):
            queue_size = audio_manager.audio_queue.qsize() if audio_manager.audio_queue else 0
        
        # Get audio manager status
        manager_status = "ready" if audio_manager.is_initialized() else "not_ready"
        
        return jsonify({
            "success": True,
            "is_speaking": is_speaking,
            "audio_manager": manager_status,
            "queue_size": queue_size,
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"Error getting audio status: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "is_speaking": False
        }), 500

@app.after_serving
async def shutdown_server(): # Renamed to avoid conflict with audio_manager.shutdown
    global audio_manager
    logger.info("Server shutdown: Cleaning up resources...")
    
    if audio_manager:
        if hasattr(audio_manager, 'shutdown') and asyncio.iscoroutinefunction(audio_manager.shutdown):
            logger.info("Shutting down audio manager...")
            await audio_manager.shutdown()
    logger.info("Server shutdown complete.")

if __name__ == '__main__':
    logger.info("Starting Claude-to-Speech TTS Server (Simplified Processor) on http://0.0.0.0:5000")
    # debug=True enables reloader, which can be problematic for resources like pygame audio.
    # use_reloader=False is generally safer for applications with external resource management.
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
