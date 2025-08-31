#!/usr/bin/env python3
"""
MCP Server-Push Notification Handler
Handles real-time TTS notifications pushed from the MCP server
"""

import asyncio
import json
import os
import subprocess
import traceback
from typing import Optional, Dict, Any
from mcp.client.session import ClientSession
import time


class NotificationClientSession(ClientSession):
    """
    Extended MCP ClientSession that handles server-pushed notifications.
    Works alongside the existing polling-based notification system.
    """
    
    def __init__(self, *args, **kwargs):
        # Extract our custom handlers before passing to parent
        self.tts_handler = kwargs.pop('tts_handler', None)
        self.display_manager = kwargs.pop('display_manager', None)
        self.audio_coordinator = kwargs.pop('audio_coordinator', None)
        self.conversation_manager = kwargs.pop('conversation_manager', None)
        
        super().__init__(*args, **kwargs)
        
        # Track notification state
        self.processing_notification = False
        self.notification_queue = asyncio.Queue()
        self.saved_display_state = None
        self.notification_task = None
        
        # Start notification processor
        self.notification_task = asyncio.create_task(self._process_notification_queue())
    
    async def _received_notification(self, notification):
        """
        Override to handle incoming notifications from MCP server.
        This is called automatically when server sends a notification.
        """
        try:
            # Let parent class handle it first
            await super()._received_notification(notification)
            
            # Check if this is a TTS notification
            if hasattr(notification, 'method'):
                if notification.method == "tts/speak":
                    await self._handle_tts_notification(notification)
                elif notification.method == "tts/announcement":
                    await self._handle_announcement_notification(notification)
                elif notification.method == "system/alert":
                    await self._handle_system_alert(notification)
                elif notification.method == "tool/use":
                    await self._handle_tool_use_notification(notification)
                    
        except Exception as e:
            print(f"[NOTIFICATION ERROR] Failed to process notification: {e}")
            traceback.print_exc()
    
    async def _handle_tts_notification(self, notification):
        """
        Handle standard TTS notification from server.
        Queues the notification for proper state management.
        """
        try:
            params = notification.params if hasattr(notification, 'params') else {}
            
            notification_data = {
                'type': 'tts',
                'text': params.get('text', ''),
                'voice': params.get('voice', 'laura'),
                'mood': params.get('mood', 'explaining'),
                'priority': params.get('priority', 'normal'),
                'interrupt': params.get('interrupt', False),
                'return_to_previous': params.get('return_to_previous', True)
            }
            
            print(f"[TTS NOTIFICATION] Received: {notification_data['text'][:50]}...")
            
            # Queue the notification for processing
            await self.notification_queue.put(notification_data)
            
        except Exception as e:
            print(f"[TTS NOTIFICATION ERROR] Failed to handle TTS notification: {e}")
    
    async def _handle_announcement_notification(self, notification):
        """
        Handle announcement notifications (higher priority).
        These interrupt current activity immediately.
        """
        try:
            params = notification.params if hasattr(notification, 'params') else {}
            
            notification_data = {
                'type': 'announcement',
                'text': params.get('text', ''),
                'voice': params.get('voice', 'laura'),
                'mood': params.get('mood', 'important'),
                'priority': 'high',
                'interrupt': True,
                'return_to_previous': True,
                'sound_effect': params.get('sound_effect', None)
            }
            
            print(f"[ANNOUNCEMENT] Received: {notification_data['text'][:50]}...")
            
            # High priority - add to front of queue
            queue_items = []
            while not self.notification_queue.empty():
                queue_items.append(await self.notification_queue.get())
            
            await self.notification_queue.put(notification_data)
            for item in queue_items:
                await self.notification_queue.put(item)
                
        except Exception as e:
            print(f"[ANNOUNCEMENT ERROR] Failed to handle announcement: {e}")
    
    async def _handle_system_alert(self, notification):
        """
        Handle system alerts (critical notifications).
        """
        try:
            params = notification.params if hasattr(notification, 'params') else {}
            
            notification_data = {
                'type': 'alert',
                'text': params.get('text', 'System alert'),
                'voice': params.get('voice', 'laura'),
                'mood': params.get('mood', 'error'),
                'priority': 'critical',
                'interrupt': True,
                'return_to_previous': False,  # Stay in alert state
                'alert_type': params.get('alert_type', 'warning')
            }
            
            print(f"[SYSTEM ALERT] {notification_data['alert_type']}: {notification_data['text']}")
            
            # Critical - process immediately
            await self._process_notification(notification_data)
            
        except Exception as e:
            print(f"[ALERT ERROR] Failed to handle system alert: {e}")
    
    async def _handle_tool_use_notification(self, notification):
        """
        Handle tool use notifications from MCP server.
        Updates display to show processing state during tool execution.
        """
        try:
            params = notification.params if hasattr(notification, 'params') else {}
            
            tool_name = params.get('tool', 'unknown')
            tool_count = params.get('count', 1)
            status = params.get('status', 'running')  # running, complete
            
            print(f"[TOOL USE] {tool_name} - {status} (tool {tool_count})")
            
            # Update display to show tool processing
            if self.display_manager and status == 'running':
                await self.display_manager.update_display('execution')
                
                # Play tool use sound if multiple tools
                if tool_count > 1:
                    try:
                        teletype_sound = "/home/user/rp_client/assets/sounds/sound_effects/teletype.mp3"
                        if os.path.exists(teletype_sound):
                            # Play sound in background
                            import subprocess
                            subprocess.Popen(['aplay', '-q', teletype_sound], 
                                           stdout=subprocess.DEVNULL, 
                                           stderr=subprocess.DEVNULL)
                    except:
                        pass
            
        except Exception as e:
            print(f"[TOOL USE ERROR] Failed to handle tool notification: {e}")
    
    async def _process_notification_queue(self):
        """
        Background task to process queued notifications with proper state management.
        """
        while True:
            try:
                # Wait for next notification
                notification_data = await self.notification_queue.get()
                
                # Process with state management
                await self._process_notification(notification_data)
                
                # Small delay between notifications
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[QUEUE ERROR] Failed to process notification queue: {e}")
                await asyncio.sleep(1)
    
    async def _process_notification(self, notification_data: Dict[str, Any]):
        """
        Process a single notification with proper display state management.
        """
        if not self.display_manager or not self.tts_handler or not self.audio_coordinator:
            print("[NOTIFICATION WARNING] Missing required components for notification processing")
            return
        
        try:
            self.processing_notification = True
            
            # Save current state if we should return to it
            if notification_data.get('return_to_previous', True):
                self.saved_display_state = self.display_manager.current_state
                self.saved_display_mood = getattr(self.display_manager, 'current_mood', None)
            
            # Handle interruption if needed
            if notification_data.get('interrupt', False):
                await self.audio_coordinator.stop_current_audio()
            
            # Update display based on notification type
            display_state = self._get_display_state_for_notification(notification_data)
            mood = notification_data.get('mood', 'explaining')
            
            await self.display_manager.update_display(display_state, mood=mood)
            
            # Play sound effect if specified
            sound_effect = notification_data.get('sound_effect')
            if sound_effect:
                # Assuming sound effects are in assets/sounds/
                sound_path = f"/home/user/rp_client/assets/sounds/{sound_effect}"
                if os.path.exists(sound_path):
                    await self.audio_coordinator.play_audio_file(sound_path)
                    await asyncio.sleep(0.5)
            
            # Generate and play TTS
            text = notification_data.get('text', '')
            voice = notification_data.get('voice', 'laura')
            
            if text:
                print(f"[TTS PROCESSING] Speaking: {text[:100]}...")
                audio_bytes, engine = await self.tts_handler.generate_audio(text, persona_name=voice)
                
                if audio_bytes:
                    await self.audio_coordinator.handle_tts_playback(audio_bytes, engine)
                    await self.audio_coordinator.wait_for_audio_completion_with_buffer()
            
            # Return to previous state if configured
            if notification_data.get('return_to_previous', True) and self.saved_display_state:
                await self.display_manager.update_display(
                    self.saved_display_state, 
                    mood=self.saved_display_mood
                )
            elif not notification_data.get('return_to_previous', True):
                # Stay in current state or go to idle
                if notification_data['type'] != 'alert':
                    await self.display_manager.update_display('idle')
            
        except Exception as e:
            print(f"[NOTIFICATION PROCESS ERROR] Failed to process notification: {e}")
            traceback.print_exc()
            # Try to recover to idle state
            try:
                await self.display_manager.update_display('idle')
            except:
                pass
        finally:
            self.processing_notification = False
    
    def _get_display_state_for_notification(self, notification_data: Dict[str, Any]) -> str:
        """
        Determine appropriate display state based on notification type.
        """
        notification_type = notification_data.get('type', 'tts')
        
        if notification_type == 'alert':
            return 'error'  # Or 'alert' if you have that state
        elif notification_type == 'announcement':
            return 'notification'
        elif notification_type == 'tts':
            # For regular TTS, use speaking state
            return 'speaking'
        else:
            return 'speaking'
    
    async def close(self):
        """
        Clean up when session closes.
        """
        if self.notification_task:
            self.notification_task.cancel()
            try:
                await self.notification_task
            except asyncio.CancelledError:
                pass
        
        await super().close()


def create_notification_session(read, write, **components):
    """
    Factory function to create a NotificationClientSession with required components.
    
    Args:
        read: Read stream from SSE client
        write: Write stream from SSE client
        **components: Required components (tts_handler, display_manager, etc.)
    
    Returns:
        NotificationClientSession instance
    """
    return NotificationClientSession(read, write, **components)