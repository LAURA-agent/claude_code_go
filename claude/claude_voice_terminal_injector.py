#!/usr/bin/env python3
"""
Claude Voice Terminal Injector
Handles voice command injection into visible Claude Code terminals
"""

import sys
import os
import time
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

def find_voice_enabled_sessions() -> list:
    """Find all voice-enabled Claude sessions by checking session info files"""
    sessions = []
    tmp_dir = Path("/tmp")
    
    for session_file in tmp_dir.glob("claude_voice_session_*"):
        try:
            with open(session_file, 'r') as f:
                session_info = json.load(f)
                # Check if process still running
                pid = session_info.get('pid')
                if pid and os.path.exists(f"/proc/{pid}"):
                    sessions.append(session_info)
                else:
                    # Clean up stale session file
                    session_file.unlink()
        except:
            pass
    
    return sessions

def inject_command_to_terminal(command: str, session_info: Dict[str, Any]) -> bool:
    """Inject command into Claude Code terminal via tmux or xdotool"""
    
    # Method 1: Try tmux first (most reliable)
    tmux_session = session_info.get('tmux_session')
    if tmux_session:
        try:
            # Check if tmux session exists
            result = subprocess.run(
                ["tmux", "has-session", "-t", tmux_session],
                capture_output=True
            )
            
            if result.returncode == 0:
                # Add visual indicator for voice command
                subprocess.run([
                    "tmux", "send-keys", "-t", tmux_session,
                    f"", "Enter"  # Clear line first
                ])
                
                # Send the actual command
                subprocess.run([
                    "tmux", "send-keys", "-t", tmux_session,
                    command, "Enter"
                ])
                
                print(f"[VOICE INJECT] ✅ Command sent to tmux session: {tmux_session}")
                return True
        except Exception as e:
            print(f"[VOICE INJECT] Error with tmux method: {e}")
    
    # Method 2: Try xdotool (for non-tmux terminals)
    pid = session_info.get('pid')
    if pid:
        try:
            # Find window by PID
            result = subprocess.run(
                ["xdotool", "search", "--pid", str(pid)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                window_id = result.stdout.strip().split('\n')[0]
                
                # Focus the window
                subprocess.run(["xdotool", "windowactivate", window_id])
                time.sleep(0.1)
                
                # Type the command
                subprocess.run(["xdotool", "type", command])
                time.sleep(0.1)
                
                # Press Enter
                subprocess.run(["xdotool", "key", "Return"])
                
                print(f"[VOICE INJECT] ✅ Command sent via xdotool to window {window_id}")
                return True
                
        except FileNotFoundError:
            print("[VOICE INJECT] xdotool not found")
        except Exception as e:
            print(f"[VOICE INJECT] Error with xdotool method: {e}")
    
    print("[VOICE INJECT] ❌ Failed to inject command - no suitable method found")
    return False

def handle_voice_command(command: str) -> Dict[str, Any]:
    """Main function to handle voice command routing to visible Claude terminal"""
    
    print(f"\n[VOICE TERMINAL] Processing command: '{command}'")
    
    # Find voice-enabled sessions
    sessions = find_voice_enabled_sessions()
    
    if not sessions:
        print("[VOICE TERMINAL] No voice-enabled Claude sessions found")
        print("[VOICE TERMINAL] Please launch Claude Code using the desktop icon first")
        return {
            "success": False,
            "error": "No voice-enabled Claude terminal found. Launch one from desktop icon.",
            "should_create_new": True
        }
    
    # Use the most recent session
    session = max(sessions, key=lambda s: s.get('created', 0))
    print(f"[VOICE TERMINAL] Found session: PID {session.get('pid')}")
    
    # Inject the command
    if inject_command_to_terminal(command, session):
        return {
            "success": True,
            "session_info": f"Voice terminal PID {session.get('pid')}",
            "message": "Command sent to visible Claude terminal"
        }
    else:
        return {
            "success": False,
            "error": "Failed to inject command into terminal",
            "session_info": f"Session PID {session.get('pid')}"
        }

if __name__ == "__main__":
    # Test mode
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        result = handle_voice_command(command)
        print(json.dumps(result, indent=2))
    else:
        # Show status
        sessions = find_voice_enabled_sessions()
        print(f"Voice-enabled Claude sessions: {len(sessions)}")
        for session in sessions:
            print(f"  - PID: {session.get('pid')}, Created: {session.get('created')}")