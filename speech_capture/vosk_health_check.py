#!/usr/bin/env python3
"""
VOSK Health Check - Native Implementation
Simple health check for native VOSK library
"""

import os
import sys
from pathlib import Path

# Add project root to path for imports when running as script
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))


async def check_vosk_server(server_url=None, timeout=30):
    """
    Check native VOSK availability (no server needed)
    
    Args:
        server_url: Ignored for compatibility
        timeout: Ignored for compatibility
        
    Returns:
        tuple: (is_healthy, message)
    """
    try:
        # Check if VOSK library is installed
        import vosk
        
        # Check if model exists
        from config.client_config import VOSK_MODEL_PATH
        
        if not os.path.exists(VOSK_MODEL_PATH):
            return False, f"VOSK model not found at: {VOSK_MODEL_PATH}"
            
        # Quick test to ensure model can be loaded
        model_path = Path(VOSK_MODEL_PATH)
        if not (model_path / 'am' / 'final.mdl').exists():
            return False, "VOSK model missing required files"
            
        return True, f"Native VOSK ready - Model: {VOSK_MODEL_PATH}"
        
    except ImportError:
        return False, "VOSK library not installed"
    except Exception as e:
        return False, f"VOSK check failed: {str(e)}"


async def wait_for_vosk_ready(server_url=None, max_wait=60, check_interval=2):
    """
    Check native VOSK immediately (no waiting needed)
    
    Args:
        server_url: Ignored for compatibility
        max_wait: Ignored for compatibility
        check_interval: Ignored for compatibility
        
    Returns:
        bool: True if VOSK ready
    """
    is_ready, message = await check_vosk_server()
    print(f"{'✅' if is_ready else '❌'} {message}")
    return is_ready


async def main():
    """Main entry point for command line usage"""
    # Simple health check for native VOSK
    is_ready, message = await check_vosk_server()
    print(f"{'✅' if is_ready else '❌'} {message}")
    sys.exit(0 if is_ready else 1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())