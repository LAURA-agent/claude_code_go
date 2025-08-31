#!/usr/bin/env python3
"""
VOSK Readiness Checker
Module to check VOSK server availability before enabling speech features
"""

import asyncio
import time
import logging
from speech_capture.vosk_health_check import check_vosk_server

logger = logging.getLogger('vosk_readiness')


class VoskReadinessChecker:
    """
    Manages VOSK server readiness state and provides safe access controls
    """
    
    def __init__(self, server_url="ws://localhost:2700", check_interval=10):
        self.server_url = server_url
        self.check_interval = check_interval
        self.is_ready = False
        self.last_check = 0
        self.checking = False
        
    async def check_readiness(self, force=False):
        """
        Check if VOSK server is ready
        
        Args:
            force: Force check even if recently checked
            
        Returns:
            bool: True if ready, False otherwise
        """
        current_time = time.time()
        
        # Avoid frequent checks unless forced
        if not force and (current_time - self.last_check) < self.check_interval:
            return self.is_ready
            
        if self.checking:
            return self.is_ready
            
        self.checking = True
        self.last_check = current_time
        
        try:
            is_ready, message = await check_vosk_server(self.server_url)
            
            if is_ready != self.is_ready:
                if is_ready:
                    logger.info(f"VOSK server became ready: {message}")
                else:
                    logger.warning(f"VOSK server not ready: {message}")
                    
            self.is_ready = is_ready
            return self.is_ready
            
        except Exception as e:
            logger.error(f"Error checking VOSK readiness: {e}")
            self.is_ready = False
            return False
        finally:
            self.checking = False
            
    async def wait_for_ready(self, timeout=60):
        """
        Wait for VOSK server to become ready
        
        Args:
            timeout: Maximum seconds to wait
            
        Returns:
            bool: True if became ready, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if await self.check_readiness(force=True):
                return True
            await asyncio.sleep(2)
            
        return False
        
    def is_speech_enabled(self):
        """
        Check if speech features should be enabled
        
        Returns:
            bool: True if speech features can be used
        """
        return self.is_ready
        
    def get_status_message(self):
        """
        Get human-readable status message
        
        Returns:
            str: Status message
        """
        if self.is_ready:
            return "VOSK server ready - Speech features enabled"
        else:
            return "VOSK server not ready - Speech features disabled"


# Global instance for use throughout the application
vosk_readiness = VoskReadinessChecker()


def is_vosk_ready():
    """
    Quick check if VOSK is ready (doesn't perform network check)
    
    Returns:
        bool: True if VOSK was ready at last check
    """
    return vosk_readiness.is_ready


async def ensure_vosk_ready(timeout=30):
    """
    Ensure VOSK server is ready, waiting if necessary
    
    Args:
        timeout: Maximum seconds to wait
        
    Returns:
        bool: True if ready, False if timeout
    """
    return await vosk_readiness.wait_for_ready(timeout)


def get_vosk_status():
    """
    Get current VOSK readiness status message
    
    Returns:
        str: Status message
    """
    return vosk_readiness.get_status_message()