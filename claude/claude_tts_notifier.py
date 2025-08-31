#!/usr/bin/env python3

import json
import time
import uuid
from pathlib import Path
from typing import Literal, Optional
import asyncio
import threading

class ClaudeTTSNotifier:
    """
    Helper class for Claude to send TTS notifications to the user.
    
    When Claude needs to ask questions, provide warnings, or draw attention
    to something important, it writes JSON files that the TTS server monitors
    and converts to speech.
    """
    
    def __init__(self, notifications_dir: str = "/home/user/rp_client/tts_notifications", display_manager=None, enable_display_coordination: bool = True):
        self.notifications_dir = Path(notifications_dir)
        self.notifications_dir.mkdir(exist_ok=True)
        self.display_manager = display_manager
        self.enable_display_coordination = enable_display_coordination
        self._tts_coordinator = None
        
        # Mood mapping for notification types
        self.mood_map = {
            "question": "curious",      # When asking questions
            "warning": "concerned",     # For warnings  
            "error": "confused",        # For errors
            "status": "casual",         # For status updates
            "confirmation": "helpful"   # For confirmations
        }
        
    @property
    def tts_coordinator(self):
        """Lazy-load TTS coordinator to avoid circular imports"""
        if self._tts_coordinator is None and self.enable_display_coordination:
            try:
                from claude.claude_tts_coordinator import get_tts_coordinator
                self._tts_coordinator = get_tts_coordinator(self.display_manager)
            except ImportError as e:
                print(f"[ClaudeTTSNotifier] Could not import TTS coordinator: {e}")
                self.enable_display_coordination = False
        return self._tts_coordinator
        
    def notify(self, 
               text: str, 
               notification_type: Literal["question", "warning", "error", "status", "confirmation"] = "status",
               priority: Literal["low", "medium", "high", "urgent"] = "medium") -> str:
        """
        Send a TTS notification to the user.
        
        Args:
            text: The message to be spoken via TTS
            notification_type: Type of notification (question, warning, error, status, confirmation)
            priority: Priority level (low, medium, high, urgent)
            
        Returns:
            message_id: Unique identifier for this notification
        """
        message_id = f"claude-{notification_type}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        
        # Get mood for this notification type
        mood = self.mood_map.get(notification_type, "casual")
        
        notification_data = {
            "timestamp": time.time(),
            "message_id": message_id,
            "text": text,
            "type": notification_type,
            "priority": priority,
            "mood": mood,
            "already_ttsd": False,
            "source": "claude_assistant"
        }
        
        # Update display with enhanced coordination if available
        if self.enable_display_coordination and self.tts_coordinator:
            try:
                # Use TTS coordinator for proper lifecycle management
                def coordinate_async():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.tts_coordinator.coordinate_tts_with_display(notification_data))
                        loop.close()
                    except Exception as e:
                        print(f"[ClaudeTTSNotifier] Error in TTS coordination: {e}")
                        
                # Run coordination in background thread to avoid blocking
                thread = threading.Thread(target=coordinate_async, daemon=True)
                thread.start()
                # Debug output disabled for cleaner console
                
            except Exception as e:
                print(f"[ClaudeTTSNotifier] Error starting TTS coordination: {e}")
                # Fallback to simple display update
                self._simple_display_update(mood)
        elif self.display_manager:
            # Fallback to simple display update
            self._simple_display_update(mood)
        
        # Write to JSON file
        notification_file = self.notifications_dir / f"{message_id}.json"
        try:
            with open(notification_file, 'w') as f:
                json.dump(notification_data, f, indent=2)
            # Debug output disabled for cleaner console
            return message_id
        except Exception as e:
            print(f"[ClaudeTTSNotifier] Error writing notification: {e}")
            return ""
    
    def ask_question(self, question: str) -> str:
        """Ask the user a question via TTS"""
        return self.notify(question, notification_type="question", priority="high")
    
    def warn_user(self, warning: str) -> str:
        """Send a warning to the user via TTS"""
        return self.notify(warning, notification_type="warning", priority="high")
    
    def report_error(self, error: str) -> str:
        """Report an error to the user via TTS"""
        return self.notify(error, notification_type="error", priority="urgent")
    
    def update_status(self, status: str, working: bool = True) -> str:
        """
        Send a status update to the user via TTS
        
        Args:
            status: The status message to speak
            working: True if actively working (execution state), False if done (idle state)
        """
        message_id = self.notify(status, notification_type="status", priority="medium")
        
        # Add state hint to help display coordination
        if message_id:
            try:
                notification_file = self.notifications_dir / f"{message_id}.json"
                if notification_file.exists():
                    with open(notification_file, 'r') as f:
                        data = json.load(f)
                    
                    # Add state hint for display coordination
                    data['state_hint'] = 'execution' if working else 'idle'
                    data['return_state'] = 'execution' if working else 'idle'
                    
                    with open(notification_file, 'w') as f:
                        json.dump(data, f, indent=2)
            except Exception as e:
                print(f"[ClaudeTTSNotifier] Error adding state hint: {e}")
                
        return message_id
    
    def request_confirmation(self, confirmation: str) -> str:
        """Request user confirmation via TTS"""
        return self.notify(confirmation, notification_type="confirmation", priority="high")
        
    def status_while_working(self, status: str) -> str:
        """Send status update while actively working (maintains execution state)"""
        return self.update_status(status, working=True)
        
    def status_when_done(self, status: str) -> str:
        """Send status update when task is complete (returns to idle state)"""
        return self.update_status(status, working=False)
        
    def working_update(self, message: str) -> str:
        """Convenience method: Send working status update"""
        return self.status_while_working(message)
        
    def completion_update(self, message: str) -> str:
        """Convenience method: Send completion status update"""
        return self.status_when_done(message)
    
    def set_display_manager(self, display_manager):
        """Set or update the display manager for this notifier"""
        self.display_manager = display_manager
        # Reset coordinator to pick up new display manager
        self._tts_coordinator = None
        print(f"[ClaudeTTSNotifier] Display manager updated, coordination {'enabled' if self.enable_display_coordination else 'disabled'}")
        
    def _simple_display_update(self, mood: str):
        """Fallback method for simple display updates without full coordination"""
        if not self.display_manager:
            return
            
        try:
            # Try to update display - handle both sync and async contexts
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Running in async context - create task
                    asyncio.create_task(self.display_manager.update_display("notification", mood=mood))
                else:
                    # Not in async context - run directly
                    loop.run_until_complete(self.display_manager.update_display("notification", mood=mood))
            except RuntimeError:
                # No event loop - create new one
                asyncio.run(self.display_manager.update_display("notification", mood=mood))
        except Exception as e:
            print(f"[ClaudeTTSNotifier] Error in simple display update: {e}")

# Global instance for easy access
tts_notifier = ClaudeTTSNotifier()