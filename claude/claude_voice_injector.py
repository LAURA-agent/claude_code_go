#!/usr/bin/env python3
"""
Claude Code Voice Injector
Uses evdev/uinput to create a virtual keyboard and automatically inject voice transcriptions
"""

import time
import sys
import os
from evdev import UInput, ecodes as e

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude.voice_input_manager import VoiceInputManager

class ClaudeVoiceInjector:
    def __init__(self):
        self.voice_manager = VoiceInputManager()
        
        # Define virtual keyboard capabilities
        self.capabilities = {
            e.EV_KEY: [
                # Letters
                e.KEY_A, e.KEY_B, e.KEY_C, e.KEY_D, e.KEY_E, e.KEY_F,
                e.KEY_G, e.KEY_H, e.KEY_I, e.KEY_J, e.KEY_K, e.KEY_L,
                e.KEY_M, e.KEY_N, e.KEY_O, e.KEY_P, e.KEY_Q, e.KEY_R,
                e.KEY_S, e.KEY_T, e.KEY_U, e.KEY_V, e.KEY_W, e.KEY_X,
                e.KEY_Y, e.KEY_Z,
                # Numbers
                e.KEY_1, e.KEY_2, e.KEY_3, e.KEY_4, e.KEY_5,
                e.KEY_6, e.KEY_7, e.KEY_8, e.KEY_9, e.KEY_0,
                # Special keys
                e.KEY_SPACE, e.KEY_ENTER, e.KEY_TAB, e.KEY_BACKSPACE,
                e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT, e.KEY_LEFTCTRL,
                # Punctuation
                e.KEY_DOT, e.KEY_COMMA, e.KEY_SEMICOLON, e.KEY_APOSTROPHE,
                e.KEY_MINUS, e.KEY_EQUAL, e.KEY_SLASH, e.KEY_BACKSLASH,
                e.KEY_LEFTBRACE, e.KEY_RIGHTBRACE, e.KEY_GRAVE
            ]
        }
        
        # Character to key mapping
        self.char_to_key = {
            'a': e.KEY_A, 'b': e.KEY_B, 'c': e.KEY_C, 'd': e.KEY_D,
            'e': e.KEY_E, 'f': e.KEY_F, 'g': e.KEY_G, 'h': e.KEY_H,
            'i': e.KEY_I, 'j': e.KEY_J, 'k': e.KEY_K, 'l': e.KEY_L,
            'm': e.KEY_M, 'n': e.KEY_N, 'o': e.KEY_O, 'p': e.KEY_P,
            'q': e.KEY_Q, 'r': e.KEY_R, 's': e.KEY_S, 't': e.KEY_T,
            'u': e.KEY_U, 'v': e.KEY_V, 'w': e.KEY_W, 'x': e.KEY_X,
            'y': e.KEY_Y, 'z': e.KEY_Z,
            '1': e.KEY_1, '2': e.KEY_2, '3': e.KEY_3, '4': e.KEY_4,
            '5': e.KEY_5, '6': e.KEY_6, '7': e.KEY_7, '8': e.KEY_8,
            '9': e.KEY_9, '0': e.KEY_0,
            ' ': e.KEY_SPACE, '\n': e.KEY_ENTER, '\t': e.KEY_TAB,
            '.': e.KEY_DOT, ',': e.KEY_COMMA, ';': e.KEY_SEMICOLON,
            "'": e.KEY_APOSTROPHE, '-': e.KEY_MINUS, '=': e.KEY_EQUAL,
            '/': e.KEY_SLASH, '\\': e.KEY_BACKSLASH,
            '[': e.KEY_LEFTBRACE, ']': e.KEY_RIGHTBRACE,
            '`': e.KEY_GRAVE
        }
        
        # Characters that require shift
        self.shift_chars = {
            'A': e.KEY_A, 'B': e.KEY_B, 'C': e.KEY_C, 'D': e.KEY_D,
            'E': e.KEY_E, 'F': e.KEY_F, 'G': e.KEY_G, 'H': e.KEY_H,
            'I': e.KEY_I, 'J': e.KEY_J, 'K': e.KEY_K, 'L': e.KEY_L,
            'M': e.KEY_M, 'N': e.KEY_N, 'O': e.KEY_O, 'P': e.KEY_P,
            'Q': e.KEY_Q, 'R': e.KEY_R, 'S': e.KEY_S, 'T': e.KEY_T,
            'U': e.KEY_U, 'V': e.KEY_V, 'W': e.KEY_W, 'X': e.KEY_X,
            'Y': e.KEY_Y, 'Z': e.KEY_Z,
            '!': e.KEY_1, '@': e.KEY_2, '#': e.KEY_3, '$': e.KEY_4,
            '%': e.KEY_5, '^': e.KEY_6, '&': e.KEY_7, '*': e.KEY_8,
            '(': e.KEY_9, ')': e.KEY_0,
            '_': e.KEY_MINUS, '+': e.KEY_EQUAL,
            ':': e.KEY_SEMICOLON, '"': e.KEY_APOSTROPHE,
            '<': e.KEY_COMMA, '>': e.KEY_DOT, '?': e.KEY_SLASH,
            '{': e.KEY_LEFTBRACE, '}': e.KEY_RIGHTBRACE,
            '|': e.KEY_BACKSLASH, '~': e.KEY_GRAVE
        }
    
    def type_text(self, ui, text):
        """Type text using the virtual keyboard"""
        print(f"[INJECTOR] Typing: '{text}'")
        
        for char in text:
            if char in self.char_to_key:
                # Regular character
                key = self.char_to_key[char]
                ui.write(e.EV_KEY, key, 1)  # Key down
                ui.write(e.EV_KEY, key, 0)  # Key up
                ui.syn()
            elif char in self.shift_chars:
                # Character requiring shift
                key = self.shift_chars[char]
                ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)  # Shift down
                ui.write(e.EV_KEY, key, 1)  # Key down
                ui.write(e.EV_KEY, key, 0)  # Key up
                ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)  # Shift up
                ui.syn()
            else:
                # Unknown character, skip or replace
                print(f"[INJECTOR] Warning: Unknown character '{char}', skipping")
                continue
            
            # Small delay between keystrokes for natural typing
            time.sleep(0.02)
    
    def paste_with_ctrl_v(self, ui):
        """Send Ctrl+V to paste from clipboard"""
        print("[INJECTOR] Sending Ctrl+V")
        ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 1)  # Ctrl down
        ui.write(e.EV_KEY, e.KEY_V, 1)         # V down
        ui.write(e.EV_KEY, e.KEY_V, 0)         # V up
        ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 0)  # Ctrl up
        ui.syn()
    
    def capture_and_inject_voice(self):
        """Main function: capture voice, transcribe, and inject into Claude Code"""
        print("[INJECTOR] Starting Claude Code voice injection...")
        print("[INJECTOR] Make sure Claude Code terminal is focused!")
        
        # Give user time to focus Claude Code window
        for i in range(5, 0, -1):
            print(f"[INJECTOR] Starting in {i} seconds...")
            time.sleep(1)
        
        try:
            # Capture voice and get transcription
            print("[INJECTOR] Capturing voice...")
            transcript = self.voice_manager.capture_voice()
            
            if not transcript:
                print("[INJECTOR] No voice captured, exiting")
                return False
            
            print(f"[INJECTOR] Transcribed: '{transcript}'")
            
            # Create virtual keyboard and inject text
            with UInput(self.capabilities, name='claude-voice-injector', version=0x3) as ui:
                print(f"[INJECTOR] Virtual keyboard created: {ui.name}")
                
                # Give system time to recognize the device
                time.sleep(0.5)
                
                # Method 1: Try direct typing
                print("[INJECTOR] Attempting direct text injection...")
                self.type_text(ui, transcript)
                
                print("[INJECTOR] Voice injection complete!")
                print("[INJECTOR] You can now review and press Enter in Claude Code")
                
                return True
                
        except Exception as e:
            print(f"[INJECTOR] Error during injection: {e}")
            import traceback
            traceback.print_exc()
            return False

def get_clipboard_text():
    """Get text from clipboard using pyclip"""
    try:
        import pyclip
        return pyclip.paste().strip()
    except Exception as e:
        print(f"[INJECTOR] Error getting clipboard: {e}")
        return None

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test mode - just type a test message
        injector = ClaudeVoiceInjector()
        with UInput(injector.capabilities, name='claude-voice-injector-test') as ui:
            time.sleep(1)
            injector.type_text(ui, "Hello from Claude Voice Injector test!")
        print("Test complete!")
        return
    
    if len(sys.argv) > 2 and sys.argv[1] == "--inject-text":
        # Inject specific text mode
        transcript = sys.argv[2]
        
        print(f"[INJECTOR] Injecting text: '{transcript}'")
        
        injector = ClaudeVoiceInjector()
        try:
            with UInput(injector.capabilities, name='claude-voice-injector', version=0x3) as ui:
                time.sleep(0.5)  # Let system recognize device
                injector.type_text(ui, transcript)  # Type the text directly
                print("✓ Text injection successful!")
        except Exception as e:
            print(f"✗ Text injection failed: {e}")
            sys.exit(1)
        return
    
    # Normal operation - capture voice and inject
    injector = ClaudeVoiceInjector()
    success = injector.capture_and_inject_voice()
    
    if success:
        print("✓ Voice injection successful!")
    else:
        print("✗ Voice injection failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()