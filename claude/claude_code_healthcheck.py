#!/usr/bin/env python3
"""
Claude Code Health Check
Tests Claude Code availability and basic functionality before routing commands
"""

import asyncio
import subprocess
import time
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from claude_tts_notifier import tts_notifier


class ClaudeCodeHealthCheck:
    """Health check system for Claude Code CLI"""
    
    def __init__(self):
        self.last_check_time = 0
        self.last_check_result = None
        self.cache_duration = 30  # Cache results for 30 seconds
        
    async def quick_health_check(self) -> Dict[str, Any]:
        """Quick health check - just version and basic availability"""
        
        # Use cached result if recent
        current_time = time.time()
        if (self.last_check_result and 
            current_time - self.last_check_time < self.cache_duration):
            return self.last_check_result
            
        start_time = time.time()
        
        try:
            # Test 1: Check if claude command exists
            # First try NVM path, then fall back to system-wide check
            nvm_claude_path = "/home/user/.nvm/versions/node/v22.15.0/bin/claude"
            if Path(nvm_claude_path).exists():
                claude_path = nvm_claude_path
            else:
                result = await asyncio.create_subprocess_exec(
                    'which', 'claude',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=5.0)
                
                if result.returncode != 0:
                    return self._create_result(False, "Claude Code command not found", start_time)
                
                claude_path = stdout.decode().strip()
            
            # Test 2: Check claude --version (quick command)
            # Set up environment with Node.js in PATH
            env = os.environ.copy()
            env['PATH'] = f"/home/user/.nvm/versions/node/v22.15.0/bin:{env.get('PATH', '')}"
            
            result = await asyncio.create_subprocess_exec(
                claude_path, '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=10.0)
            
            if result.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                return self._create_result(False, f"Claude --version failed: {error_msg}", start_time)
            
            version_info = stdout.decode().strip()
            
            # Success - version check is sufficient for health check
            health_result = self._create_result(
                True, 
                f"Claude Code healthy - {version_info}", 
                start_time,
                {
                    "claude_path": claude_path,
                    "version": version_info
                }
            )
            
            # Cache the result
            self.last_check_time = current_time
            self.last_check_result = health_result
            
            return health_result
            
        except asyncio.TimeoutError:
            return self._create_result(False, "Claude Code health check timed out", start_time)
        except Exception as e:
            return self._create_result(False, f"Health check error: {str(e)}", start_time)
    
    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """More thorough health check including file operations"""
        
        # Start with quick check
        quick_result = await self.quick_health_check()
        if not quick_result["healthy"]:
            return quick_result
            
        start_time = time.time()
        
        try:
            # Test file operations in a temp directory
            test_dir = Path("/tmp/claude_health_test")
            test_dir.mkdir(exist_ok=True)
            
            test_file = test_dir / "test.txt"
            test_file.write_text("# Test file for health check\nprint('Hello, World!')\n")
            
            # Test Claude Code with file context
            # Get claude path from quick check result
            claude_path = quick_result.get("claude_path", "/home/user/.nvm/versions/node/v22.15.0/bin/claude")
            
            # Set up environment with Node.js in PATH
            env = os.environ.copy()
            env['PATH'] = f"/home/user/.nvm/versions/node/v22.15.0/bin:{env.get('PATH', '')}"
            
            result = await asyncio.create_subprocess_exec(
                claude_path, 'what is in this directory?',
                cwd=test_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=30.0)
            
            # Cleanup
            test_file.unlink()
            test_dir.rmdir()
            
            if result.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                return self._create_result(False, f"File operation test failed: {error_msg}", start_time)
            
            response = stdout.decode().strip()
            
            return self._create_result(
                True,
                "Claude Code comprehensive check passed",
                start_time,
                {
                    "test_response_length": len(response),
                    "test_response_preview": response[:200] + "..." if len(response) > 200 else response
                }
            )
            
        except asyncio.TimeoutError:
            return self._create_result(False, "Comprehensive health check timed out", start_time)
        except Exception as e:
            return self._create_result(False, f"Comprehensive check error: {str(e)}", start_time)
    
    def _create_result(self, healthy: bool, message: str, start_time: float, extra_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Create standardized health check result"""
        result = {
            "healthy": healthy,
            "message": message,
            "check_duration": time.time() - start_time,
            "timestamp": time.time()
        }
        
        if extra_data:
            result.update(extra_data)
            
        return result
    
    async def wait_for_healthy(self, max_attempts: int = 3, delay: float = 2.0) -> Dict[str, Any]:
        """Wait for Claude Code to become healthy"""
        
        for attempt in range(max_attempts):
            if attempt > 0:
                print(f"[Health Check] Attempt {attempt + 1}/{max_attempts}")
                await asyncio.sleep(delay)
                
            result = await self.quick_health_check()
            if result["healthy"]:
                return result
                
        # All attempts failed
        return result


class ClaudeCodeHealthCheckMiddleware:
    """Middleware that performs health checks before command execution"""
    
    def __init__(self):
        self.health_checker = ClaudeCodeHealthCheck()
        
    async def execute_with_health_check(self, command: str, comprehensive: bool = False) -> Dict[str, Any]:
        """Execute command with pre-flight health check"""
        
        print(f"[INFO] Claude Code health check starting...")
        cmd_preview = command[:50] + ('...' if len(command) > 50 else '')
        print(f"[INFO] Command: '{cmd_preview}'")
        
        # Choose health check type
        if comprehensive:
            health_result = await self.health_checker.comprehensive_health_check()
        else:
            health_result = await self.health_checker.quick_health_check()
            
        # Result logging in LAURA format
        if health_result["healthy"]:
            print(f"[INFO] Claude Code health check passed - {health_result['message']}")
            print(f"[INFO] Duration: {health_result['check_duration']:.2f}s")
        else:
            print(f"[ERROR] Claude Code health check failed: {health_result['message']}")
            print(f"[ERROR] Duration: {health_result['check_duration']:.2f}s")
            tts_notifier.report_error(f"Claude Code unavailable: {health_result['message']}")
            return {
                "success": False,
                "error": f"Health check failed: {health_result['message']}",
                "health_check": health_result
            }
        
        # Import and execute the actual command
        try:
            print(f"[INFO] Starting Claude Code session management...")
            from claude_session_manager import handle_claude_code_with_session_management
            result = await handle_claude_code_with_session_management(command)
            
            # Log execution results in LAURA format
            if result.get('success'):
                print(f"[INFO] Claude Code command completed successfully")
                if result.get('execution_time'):
                    print(f"[INFO] Execution time: {result['execution_time']:.2f}s")
            else:
                print(f"[ERROR] Claude Code command failed: {result.get('error', 'Unknown error')}")
            
            # Add health check info to result
            result["health_check"] = health_result
            return result
            
        except Exception as e:
            print(f"[ERROR] Claude Code execution exception: {str(e)}")
            return {
                "success": False,
                "error": f"Command execution failed: {str(e)}",
                "health_check": health_result
            }


# Integration function for run_v2.py
async def execute_claude_code_with_health_check(command: str, comprehensive: bool = False) -> Dict[str, Any]:
    """
    Main entry point with health checking
    
    Args:
        command: The voice command to execute
        comprehensive: Whether to do comprehensive health check
        
    Returns:
        Dict with execution results and health check info
    """
    middleware = ClaudeCodeHealthCheckMiddleware()
    return await middleware.execute_with_health_check(command, comprehensive)


# Command line testing
if __name__ == "__main__":
    async def test_health_check():
        """Test the health check system"""
        checker = ClaudeCodeHealthCheck()
        
        print("=== Quick Health Check ===")
        result = await checker.quick_health_check()
        print(json.dumps(result, indent=2))
        
        if result["healthy"]:
            print("\n=== Comprehensive Health Check ===")
            result = await checker.comprehensive_health_check()
            print(json.dumps(result, indent=2))
        
        print("\n=== Testing Middleware ===")
        middleware = ClaudeCodeHealthCheckMiddleware()
        result = await middleware.execute_with_health_check("what is 2+2?")
        print(f"Command result: {result.get('success', False)}")
        if result.get('response'):
            print(f"Response: {result['response'][:100]}...")
    
    asyncio.run(test_health_check())