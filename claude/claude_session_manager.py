#!/usr/bin/env python3
"""
Claude Code Session Manager
Detects existing Claude Code sessions and communicates with them
"""

import asyncio
import psutil
import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from claude_tts_notifier import tts_notifier


class ClaudeSession:
    """Represents a detected Claude Code session"""
    
    def __init__(self, pid: int, cwd: str, cmdline: List[str]):
        self.pid = pid
        self.cwd = Path(cwd) if cwd else Path.cwd()
        self.cmdline = cmdline
        self.created_at = time.time()
        
    def __str__(self):
        return f"Claude session PID {self.pid} in {self.cwd}"
        
    def is_alive(self) -> bool:
        """Check if the process is still running"""
        try:
            proc = psutil.Process(self.pid)
            return proc.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False


class ClaudeSessionManager:
    """Manages communication with existing Claude Code sessions"""
    
    def __init__(self):
        self.communication_timeout = 10.0  # 10 second timeout for file communication
        
    def find_existing_claude_sessions(self) -> List[ClaudeSession]:
        """Find all running Claude Code processes"""
        claude_sessions = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
            try:
                proc_info = proc.info
                proc_name = proc_info.get('name', '').lower()
                cmdline = proc_info.get('cmdline', [])
                
                # Look for Claude Code processes
                if ('claude' in proc_name or 
                    (cmdline and 'claude' in cmdline[0].lower())):
                    
                    # Skip our own voice wrapper processes
                    if any('voice' in str(arg).lower() for arg in cmdline):
                        continue
                        
                    session = ClaudeSession(
                        pid=proc_info['pid'],
                        cwd=proc_info.get('cwd'),
                        cmdline=cmdline
                    )
                    claude_sessions.append(session)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
                continue
                
        return claude_sessions
    
    async def select_session(self, sessions: List[ClaudeSession]) -> Optional[ClaudeSession]:
        """Let user select which session to use (or create new one)"""
        if not sessions:
            return None
            
        if len(sessions) == 1:
            session = sessions[0]
            tts_notifier.ask_question(
                f"Found Claude Code running in {session.cwd.name}. Use this session?"
            )
            # For now, assume yes. Could implement user response handling
            return session
            
        # Multiple sessions - for now just use the first one
        # Could be enhanced to let user choose
        session = sessions[0]
        tts_notifier.ask_question(
            f"Found {len(sessions)} Claude sessions. Using the one in {session.cwd.name}"
        )
        return session
    
    async def send_command_to_session(self, session: ClaudeSession, command: str) -> Dict[str, Any]:
        """Send voice command to existing Claude session via file communication"""
        
        try:
            # Verify session is still alive
            if not session.is_alive():
                return {
                    "success": False,
                    "error": "Claude session is no longer running",
                    "fallback_to_new": True
                }
            
            # Create command file in Claude's working directory
            command_file = session.cwd / ".claude_voice_command.json"
            response_file = session.cwd / ".claude_voice_response.json"
            
            # Clean up any existing files
            if command_file.exists():
                command_file.unlink()
            if response_file.exists():
                response_file.unlink()
                
            # Write command
            command_data = {
                "timestamp": time.time(),
                "command": command,
                "source": "voice_input",
                "session_pid": session.pid
            }
            
            with open(command_file, 'w') as f:
                json.dump(command_data, f, indent=2)
                
            print(f"[Session Manager] Sent command to {session}")
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < self.communication_timeout:
                if response_file.exists():
                    try:
                        with open(response_file, 'r') as f:
                            response_data = json.load(f)
                            
                        # Clean up files
                        command_file.unlink()
                        response_file.unlink()
                        
                        return {
                            "success": True,
                            "response": response_data.get("response", ""),
                            "execution_time": response_data.get("execution_time", 0),
                            "session_info": str(session)
                        }
                        
                    except (json.JSONDecodeError, IOError) as e:
                        print(f"[Session Manager] Error reading response: {e}")
                        continue
                        
                await asyncio.sleep(0.5)
                
                # Check if session is still alive
                if not session.is_alive():
                    break
                    
            # Timeout or session died
            # Clean up files
            if command_file.exists():
                command_file.unlink()
            if response_file.exists():
                response_file.unlink()
                
            return {
                "success": False,
                "error": "No response from Claude session (timeout or session ended)",
                "fallback_to_new": True
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to communicate with session: {str(e)}",
                "fallback_to_new": True
            }
    
    async def handle_voice_command(self, command: str) -> Dict[str, Any]:
        """Main entry point for handling voice commands with session management"""
        
        try:
            # Find existing Claude sessions
            sessions = self.find_existing_claude_sessions()
            
            if sessions:
                print(f"[Session Manager] Found {len(sessions)} existing Claude session(s)")
                
                # Select which session to use
                selected_session = await self.select_session(sessions)
                
                if selected_session:
                    # Try to send command to existing session
                    result = await self.send_command_to_session(selected_session, command)
                    
                    if result["success"]:
                        tts_notifier.update_status("Command executed in existing Claude session")
                        return result
                    elif result.get("fallback_to_new"):
                        tts_notifier.warn_user("Existing session unavailable, starting new Claude instance")
                        # Fall through to create new session
                    else:
                        return result
            
            # No existing sessions or fallback needed - create new one
            print("[Session Manager] Creating new Claude Code session")
            return await self._create_new_session(command)
            
        except Exception as e:
            error_msg = f"Session management error: {str(e)}"
            print(f"[Session Manager] {error_msg}")
            tts_notifier.report_error(error_msg)
            return {"success": False, "error": error_msg}
    
    async def _create_new_session(self, command: str) -> Dict[str, Any]:
        """Create new Claude Code session (fallback)"""
        start_time = time.time()
        
        try:
            # Use the original subprocess approach for new sessions
            process = await asyncio.create_subprocess_exec(
                'claude',
                command,
                cwd=Path.cwd(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=300.0
            )
            
            execution_time = time.time() - start_time
            
            if process.returncode == 0:
                response = stdout.decode('utf-8').strip()
                return {
                    "success": True,
                    "response": response,
                    "execution_time": execution_time,
                    "session_info": "New Claude session"
                }
            else:
                error = stderr.decode('utf-8').strip()
                return {
                    "success": False,
                    "error": f"Claude Code error: {error}",
                    "execution_time": execution_time
                }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "New Claude session timed out",
                "execution_time": 300.0
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create new Claude session: {str(e)}",
                "execution_time": time.time() - start_time
            }


# Integration function for run_v2.py
async def handle_claude_code_with_session_management(transcript: str) -> Dict[str, Any]:
    """
    Enhanced Claude Code handler with session management
    
    Args:
        transcript: Voice transcript to process
        
    Returns:
        Dict with processing results
    """
    # First, check for voice-enabled visible terminals
    try:
        from claude_voice_terminal_injector import handle_voice_command as handle_terminal_inject
        
        print("[Session Manager] Checking for voice-enabled terminals...")
        terminal_result = handle_terminal_inject(transcript)
        
        if terminal_result.get("success"):
            print(f"[Session Manager] Command sent to visible terminal: {terminal_result.get('message')}")
            return {
                "success": True,
                "response": "Command sent to Claude terminal",
                "execution_time": 0.5,
                "session_info": terminal_result.get("session_info", "Voice terminal"),
                "terminal_mode": True
            }
        elif terminal_result.get("should_create_new"):
            print("[Session Manager] No voice terminal found - please launch from desktop icon")
            tts_notifier.warn_user("Please launch Claude Code from the desktop icon first")
            return {
                "success": False,
                "error": "No voice-enabled terminal found. Please launch Claude Code from desktop icon.",
                "execution_time": 0.1
            }
    except Exception as e:
        print(f"[Session Manager] Terminal injection check failed: {e}")
    
    # Fall back to original session management if no voice terminal
    manager = ClaudeSessionManager()
    return await manager.handle_voice_command(transcript)


# Command line testing
if __name__ == "__main__":
    async def test_session_manager():
        """Test the session manager"""
        manager = ClaudeSessionManager()
        
        # Test session detection
        sessions = manager.find_existing_claude_sessions()
        print(f"Found {len(sessions)} Claude sessions:")
        for session in sessions:
            print(f"  {session}")
            
        # Test command handling
        if sessions:
            result = await manager.handle_voice_command("what files are in this directory?")
            print(f"Result: {result}")
        else:
            print("No existing sessions found - would create new one")
    
    asyncio.run(test_session_manager())