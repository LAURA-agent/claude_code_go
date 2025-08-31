#!/usr/bin/env python3

import asyncio
import json
import os
import random
import time
from typing import Optional


class NotificationManager:
    """
    Manages notification checking, processing, and display coordination.
    
    Handles server notification polling, notification audio/TTS coordination,
    and proper display state management during notification events.
    """
    
    def __init__(self, audio_coordinator, tts_handler):
        self.audio_coordinator = audio_coordinator
        self.tts_handler = tts_handler
        self.connection_status = "unknown"  # Track MCP connection status
        self.last_successful_check = None   # Track last successful notification check
        self.consecutive_failures = 0       # Track consecutive failures for backoff

    async def check_for_notifications(self, mcp_session, session_id):
        """Check for server notifications once"""
        if not mcp_session or not session_id:
            return
        
        try:
            response = await mcp_session.call_tool("check_notifications", 
                                                  arguments={"session_id": session_id})
            
            # Parse response properly
            notifications = None
            if hasattr(response, 'content') and response.content:
                json_str = response.content[0].text
                parsed_response = json.loads(json_str)
                notifications = parsed_response.get("notifications", [])
            elif isinstance(response, dict):
                notifications = response.get("notifications", [])
            
            # Update connection status on successful response
            self.connection_status = "connected"
            self.consecutive_failures = 0
            self.last_successful_check = asyncio.get_event_loop().time()
            
            if notifications:
                print(f"[NOTIFICATION] Found {len(notifications)} notifications")
                return notifications
                    
        except Exception as e:
            print(f"[NOTIFICATION ERROR] Failed to check notifications: {e}")
            print(f"[NOTIFICATION ERROR] Exception type: {type(e)}")
            if hasattr(e, 'message'):
                print(f"[NOTIFICATION ERROR] Exception message: {e.message}")
            # Update connection status and failure count
            self.consecutive_failures += 1
            
            # Check if it's a specific MCP error
            if "tool" in str(e).lower() and "not found" in str(e).lower():
                print("[NOTIFICATION ERROR] The 'check_notifications' tool is not available on the MCP server")
                self.connection_status = "tool_missing"
            elif "connection" in str(e).lower():
                print("[NOTIFICATION ERROR] MCP connection issue detected")
                self.connection_status = "connection_failed"
            else:
                print(f"[NOTIFICATION ERROR] Full error details: {repr(e)}")
                self.connection_status = "error"
            
            print(f"[NOTIFICATION ERROR] Connection status: {self.connection_status}, consecutive failures: {self.consecutive_failures}")
            
            # Return empty list to continue operation
            return []
        
        return []

    async def handle_notification(self, notification, display_manager):
        """Handle incoming notification with TTS and display"""
        notification_type = notification.get("notification_type", "general")
        text = notification.get("text", "")
        minutes_late = notification.get("minutes_late", 0)
        
        print(f"[NOTIFICATION] {notification_type}: {text} (late: {minutes_late}min)")
        
        # Interrupt current activity for notifications
        current_state = display_manager.current_state
        
        # Stop any current audio
        await self.audio_coordinator.stop_current_audio()
        
        # Determine mood and sound based on how late the medicine is
        if notification_type == "medicine_reminder":
            base_path = "/home/user/rp_client/assets/sounds/laura/notifications/daily_medicine"
            
            # Progressive anger based on lateness
            if minutes_late >= 30:
                # Over 30 minutes - very angry/sassy
                mood = "annoyed"  # This should trigger angry images
                timeout_sounds = [
                    f"{base_path}/over30/getdistracted.mp3",
                    f"{base_path}/over30/notasfunctional.mp3", 
                    f"{base_path}/over30/quitbeingloser.mp3"
                ]
                notification_audio = random.choice([s for s in timeout_sounds if os.path.exists(s)])
            elif minutes_late >= 20:
                mood = "frustrated"  # Frustrated images
                notification_audio = f"{base_path}/20min.mp3"
            elif minutes_late >= 10:
                mood = "concerned"   # Concerned images
                notification_audio = f"{base_path}/10min.mp3"
            else:
                mood = "caring"      # Caring images for initial reminder
                notification_audio = f"{base_path}/notification.mp3"
        else:
            mood = notification.get("mood", "caring")
            notification_audio = None
        
        # Update display to notification state with appropriate mood
        await display_manager.update_display("notification", mood=mood)
        
        # Play notification sound if available
        if notification_audio and os.path.exists(notification_audio):
            await self.audio_coordinator.play_audio_file(notification_audio)
            await asyncio.sleep(1)  # Brief pause between notification sound and TTS
        
        # Generate and play TTS (display state set to notification with mood)
        if text:
            audio_bytes, engine = await self.tts_handler.generate_audio(text, persona_name="laura")
            if audio_bytes:
                await self.audio_coordinator.handle_tts_playback(audio_bytes, engine)
        
        # Return to previous state or idle
        await self.audio_coordinator.wait_for_audio_completion_with_buffer()
        if current_state in ['sleep', 'idle']:
            await display_manager.update_display(current_state)
        else:
            await display_manager.update_display("idle")

    async def process_notifications(self, notifications, display_manager):
        """Process a list of notifications"""
        for notification in notifications:
            await self.handle_notification(notification, display_manager)

    async def check_for_notifications_loop(self, mcp_session, session_id, display_manager):
        """Background notification checking with exponential backoff on failures"""
        base_interval = 30  # Base check interval in seconds
        
        while True:
            # Calculate delay based on consecutive failures (exponential backoff)
            if self.consecutive_failures == 0:
                delay = base_interval
            else:
                # Exponential backoff: 30s, 60s, 120s, 240s, max 300s (5min)
                delay = min(base_interval * (2 ** (self.consecutive_failures - 1)), 300)
            
            await asyncio.sleep(delay)
            
            notifications = await self.check_for_notifications(mcp_session, session_id)
            if notifications:
                await self.process_notifications(notifications, display_manager)

    async def test_local_notification(self, display_manager, notification_type="medicine_reminder", minutes_late=0):
        """Test the notification system locally without MCP server"""
        print(f"[NOTIFICATION TEST] Testing local notification: {notification_type}, {minutes_late} min late")
        
        test_notification = {
            "notification_type": notification_type,
            "text": f"Test {notification_type} notification - {minutes_late} minutes late",
            "minutes_late": minutes_late,
            "timestamp": time.time()
        }
        
        await self.handle_notification(test_notification, display_manager)
        
    def get_connection_status(self):
        """Get current connection status and diagnostics"""
        return {
            "status": self.connection_status,
            "consecutive_failures": self.consecutive_failures,
            "last_successful_check": self.last_successful_check,
            "time_since_success": (
                time.time() - self.last_successful_check 
                if self.last_successful_check else None
            )
        }