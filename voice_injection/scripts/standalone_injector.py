#!/usr/bin/env python3
"""
Standalone Voice Injector - No external dependencies
Simple virtual keyboard for text injection
"""

import time
from evdev import UInput, ecodes as e

class StandaloneInjector:
    def __init__(self):
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
                e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT,
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
                # Unknown character, skip
                print(f"[INJECTOR] Warning: Unknown character '{char}', skipping")
                continue
            
            # Small delay between keystrokes for natural typing
            time.sleep(0.02)
    
    def inject_text(self, text):
        """Inject text using virtual keyboard"""
        try:
            with UInput(self.capabilities, name='standalone-injector', version=0x3) as ui:
                # Give system time to recognize device
                time.sleep(0.2)
                
                # Type the text
                self.type_text(ui, text)
                
                print(f"[INJECTOR] Successfully injected text")
                return True
                
        except Exception as e:
            print(f"[INJECTOR] Error injecting text: {e}")
            return False

# Make it importable and runnable
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 standalone_injector.py 'text to inject'")
        sys.exit(1)
    
    text = sys.argv[1]
    injector = StandaloneInjector()
    
    print("Focus your target window in 3 seconds...")
    time.sleep(3)
    
    if injector.inject_text(text):
        print("✓ Text injection successful!")
    else:
        print("✗ Text injection failed!")
        sys.exit(1)