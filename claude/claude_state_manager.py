#!/usr/bin/env python3

import json
import time
import os
from pathlib import Path
from typing import Optional

class ClaudeStateManager:
    """
    Simple helper to manage display states for Claude Code interactions.
    Works like ClaudeTTSNotifier but for display state coordination.
    """
    
    def __init__(self, notifications_dir: str = "/home/user/rp_client/tts_notifications"):
        self.notifications_dir = Path(notifications_dir)
        self.notifications_dir.mkdir(exist_ok=True)
        
    def set_execution_state(self, message: str = "Working on task"):
        """Set display to execution state"""
        self._send_state_notification("execution", message)
    
    def set_idle_state(self, message: str = "Task completed, ready for next request"):
        """Set display to idle state - only when truly done"""  
        self._send_state_notification("idle", message)
        
    def set_thinking_state(self, message: str = "Processing request"):
        """Set display to thinking state"""
        self._send_state_notification("thinking", message)
        
    def _send_state_notification(self, state: str, message: str):
        """Send state change notification to the system"""
        try:
            # Use the global TTS notifier instance that has display manager configured
            from claude.claude_tts_notifier import tts_notifier
            
            # Send notification with state hint
            if state == 'execution':
                tts_notifier.working_update(message)
            elif state == 'idle': 
                tts_notifier.completion_update(message)
            else:
                tts_notifier.update_status(message)
                
            print(f"[ClaudeStateManager] Set {state} state: {message}")
            
        except Exception as e:
            print(f"[ClaudeStateManager] Error setting {state} state: {e}")

# Global instance for easy access
state_manager = ClaudeStateManager()

# Convenience functions
def set_execution_state(message: str = "Working on task"):
    """Quick helper: Set execution state"""
    state_manager.set_execution_state(message)

def set_idle_state(message: str = "Ready for next request"):
    """Quick helper: Set idle state - only when truly done"""
    state_manager.set_idle_state(message)
    
def set_thinking_state(message: str = "Processing request"):
    """Quick helper: Set thinking state"""
    state_manager.set_thinking_state(message)