#!/usr/bin/env python3
"""
Speak - Robust TTS interface with graceful error handling
Improved version of tts_helper with better timeout management and retry logic
"""

import requests
import json
import re
import os
import sys
import time
from typing import Optional, Tuple

# Add parent directory to path for imports
sys.path.append('/home/user/rp_client')

# Configuration
DEFAULT_TIMEOUT = 10.0  # Increased from 5 seconds
RETRY_ATTEMPTS = 2
RETRY_DELAY = 0.5
SERVER_URL = "http://localhost:5000/tts"
VOICE_ID = "qEwI395unGwWV1dn3Y65"  # Claude Code voice

def clean_text_for_speech(text: str) -> str:
    """Clean text for better TTS pronunciation"""
    # Replace common phrases that sound robotic
    text = text.replace("You're absolutely right", "You're right")
    
    # Replace underscores with spaces
    text = text.replace('_', ' ')
    
    # Handle dots between text (e.g., "file.txt" -> "file dot txt")
    text = re.sub(r'(\w)\.(\w)', r'\1 dot \2', text)
    
    # Remove problematic symbols while keeping natural punctuation
    # Keep: ! ? , : ; . for natural speech flow
    symbols_to_remove = r'[\\|}{[\]/%*#@$^&+=<>~`"()]'
    text = re.sub(symbols_to_remove, ' ', text)
    
    # Handle hyphens intelligently
    text = re.sub(r'\s+-\s+', ' ', text)  # Remove spaced hyphens
    text = re.sub(r'^-\s+', '', text)     # Remove leading hyphen
    text = re.sub(r'\s+-$', '', text)     # Remove trailing hyphen
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def send_tts_request(text: str, timeout: float = DEFAULT_TIMEOUT) -> Tuple[bool, str]:
    """
    Send TTS request with proper error handling
    Returns (success, error_message)
    """
    try:
        response = requests.post(
            SERVER_URL,
            headers={"Content-Type": "application/json"},
            json={"text": text, "voice": VOICE_ID},
            timeout=timeout
        )
        
        if response.status_code == 200:
            return True, ""
        else:
            return False, f"Server returned {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, f"Timeout after {timeout}s"
    except requests.exceptions.ConnectionError:
        return False, "Connection failed - server may be down"
    except Exception as e:
        return False, str(e)

def speak_with_retry(text: str, mode: str = "conversation", 
                    timeout: float = DEFAULT_TIMEOUT,
                    retries: int = RETRY_ATTEMPTS) -> bool:
    """
    Speak text with automatic retry on failure
    
    Args:
        text: Text to speak
        mode: Either 'conversation' or 'working'
        timeout: Timeout for each attempt
        retries: Number of retry attempts
    
    Returns:
        True if successful, False otherwise
    """
    cleaned_text = clean_text_for_speech(text)
    
    for attempt in range(retries + 1):
        # Use progressive timeout - longer for each retry
        current_timeout = timeout * (1 + attempt * 0.5)
        
        success, error = send_tts_request(cleaned_text, current_timeout)
        
        if success:
            print(f"🔊 TTS ({mode}): {cleaned_text}")
            return True
        
        # If this isn't the last attempt, retry
        if attempt < retries:
            if "Timeout" in error:
                print(f"⏱️  TTS timeout (attempt {attempt + 1}/{retries + 1}), retrying with {current_timeout + timeout * 0.5}s timeout...")
            else:
                print(f"⚠️  TTS error (attempt {attempt + 1}/{retries + 1}): {error}, retrying...")
            time.sleep(RETRY_DELAY)
        else:
            # Final failure - be graceful about it
            if "Timeout" in error:
                print(f"⏱️  TTS timeout after {retries + 1} attempts - server may be busy")
            elif "Connection" in error:
                print(f"🔌 TTS server appears to be down")
            else:
                print(f"❌ TTS failed: {error}")
    
    return False

def speak_conversation(text: str, **kwargs) -> bool:
    """Send TTS that returns to idle state - for questions/confirmations"""
    return speak_with_retry(text, mode="conversation", **kwargs)

def speak_working(text: str, **kwargs) -> bool:
    """Send TTS that maintains execution state - for status updates while working"""
    return speak_with_retry(text, mode="working", **kwargs)

def speak(text: str, voice: str = "claude", working: bool = False, 
         mood: Optional[str] = None, **kwargs) -> bool:
    """
    Legacy speak function for backwards compatibility
    
    Args:
        text: Text to speak
        voice: Voice selection (ignored, uses Claude voice)
        working: If True, maintains execution state
        mood: Mood selection (for future display integration)
        **kwargs: Additional arguments passed to speak functions
    """
    if working:
        return speak_working(text, **kwargs)
    else:
        return speak_conversation(text, **kwargs)

def main():
    """Command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Robust TTS interface')
    parser.add_argument('text', nargs='*', help='Text to speak')
    parser.add_argument('--working', action='store_true', 
                       help='Use working mode (maintains execution state)')
    parser.add_argument('--conversation', action='store_true',
                       help='Use conversation mode (returns to idle state)')
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT,
                       help=f'Timeout in seconds (default: {DEFAULT_TIMEOUT})')
    parser.add_argument('--retries', type=int, default=RETRY_ATTEMPTS,
                       help=f'Number of retry attempts (default: {RETRY_ATTEMPTS})')
    parser.add_argument('--no-retry', action='store_true',
                       help='Disable retry logic')
    
    args = parser.parse_args()
    
    if not args.text:
        print("Usage: python speak.py 'text to speak'")
        print("       python speak.py --conversation 'text for idle state'")
        print("       python speak.py --working 'text for execution state'")
        print("\nOptions:")
        print("  --timeout N     Set timeout to N seconds")
        print("  --retries N     Set retry attempts to N")
        print("  --no-retry      Disable retry logic")
        return
    
    text = " ".join(args.text)
    retries = 0 if args.no_retry else args.retries
    
    if args.working:
        speak_working(text, timeout=args.timeout, retries=retries)
    elif args.conversation:
        speak_conversation(text, timeout=args.timeout, retries=retries)
    else:
        # Default to conversation mode
        speak_conversation(text, timeout=args.timeout, retries=retries)

if __name__ == "__main__":
    main()