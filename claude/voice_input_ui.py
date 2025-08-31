#!/usr/bin/env python3
"""
Claude Code Voice Input UI
Simple touchscreen interface for voice input on Pi 4" display
"""

import tkinter as tk
from tkinter import ttk
import asyncio
import threading
from datetime import datetime
from claude.voice_input_manager import VoiceInputManager


class VoiceInputUI:
    """Simple touchscreen UI for voice input"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.voice_manager = VoiceInputManager()
        self.is_capturing = False
        
        self._setup_ui()
        self._setup_hotkeys()
        
    def _setup_ui(self):
        """Setup the touchscreen interface"""
        self.root.title("Claude Code Voice Input")
        self.root.geometry("400x240")  # Fits 4" touchscreen
        self.root.configure(bg='#2d2d2d')
        
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(expand=True, fill='both', padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="🎤 Claude Code Voice Input", 
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready to capture voice", 
                                     font=('Arial', 10))
        self.status_label.pack(pady=(0, 10))
        
        # Main voice button
        self.voice_button = tk.Button(main_frame, 
                                     text="🎤 START VOICE CAPTURE",
                                     font=('Arial', 12, 'bold'),
                                     bg='#4CAF50', fg='white',
                                     activebackground='#45a049',
                                     height=3, width=25,
                                     command=self._on_voice_button_click)
        self.voice_button.pack(pady=10)
        
        # Hotkey info
        hotkey_label = ttk.Label(main_frame, 
                                text="Hotkey: Ctrl+Start | Wake Word: 'Claude Code'",
                                font=('Arial', 8))
        hotkey_label.pack(pady=(10, 0))
        
        # Last transcription display (scrollable)
        self.transcript_text = tk.Text(main_frame, height=4, width=50,
                                      font=('Arial', 9),
                                      bg='#f0f0f0', wrap=tk.WORD)
        self.transcript_text.pack(pady=(10, 0), fill='x')
        
        # Progress bar (hidden initially)
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        
    def _setup_hotkeys(self):
        """Setup keyboard hotkey monitoring"""
        def voice_capture_callback():
            self._trigger_voice_capture()
            
        self.voice_manager.start_hotkey_monitoring(voice_capture_callback)
        
    def _on_voice_button_click(self):
        """Handle voice button click"""
        if not self.is_capturing:
            self._trigger_voice_capture()
        else:
            self._stop_voice_capture()
            
    def _trigger_voice_capture(self):
        """Start voice capture"""
        if self.is_capturing:
            return
            
        self.is_capturing = True
        self._update_ui_capturing(True)
        
        # Run voice capture in background thread
        def capture_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    self.voice_manager.capture_voice_for_clipboard(duration=60)
                )
                
                # Update UI on main thread
                self.root.after(0, lambda: self._on_capture_complete(result))
                
            except Exception as e:
                self.root.after(0, lambda: self._on_capture_error(str(e)))
            finally:
                loop.close()
                
        threading.Thread(target=capture_thread, daemon=True).start()
        
    def _stop_voice_capture(self):
        """Stop voice capture early"""
        # For now, we'll let it timeout naturally
        # Could implement early stopping if needed
        pass
        
    def _update_ui_capturing(self, capturing: bool):
        """Update UI state for capturing"""
        if capturing:
            self.voice_button.config(text="🛑 CAPTURING... (60s max)",
                                   bg='#f44336')
            self.status_label.config(text="🎤 Listening... Speak now!")
            self.progress.pack(pady=(5, 0), fill='x')
            self.progress.start()
        else:
            self.voice_button.config(text="🎤 START VOICE CAPTURE",
                                   bg='#4CAF50')
            self.status_label.config(text="Ready to capture voice")
            self.progress.stop()
            self.progress.pack_forget()
            
    def _on_capture_complete(self, result: str):
        """Handle successful voice capture"""
        self.is_capturing = False
        self._update_ui_capturing(False)
        
        if result:
            self.status_label.config(text="✅ Copied to clipboard! Press Ctrl+Shift+V to paste")
            self.transcript_text.delete(1.0, tk.END)
            self.transcript_text.insert(1.0, f"[{datetime.now().strftime('%H:%M:%S')}] {result}")
        else:
            self.status_label.config(text="❌ No speech detected")
            
    def _on_capture_error(self, error: str):
        """Handle voice capture error"""
        self.is_capturing = False
        self._update_ui_capturing(False)
        self.status_label.config(text=f"❌ Error: {error}")
        
    def run(self):
        """Start the UI"""
        print("🖥️ Starting touchscreen voice input UI...")
        print("   - Touch the button to start voice capture")
        print("   - Or use Ctrl+Start hotkey")
        print("   - Or say 'Claude Code' wake word")
        
        try:
            self.root.mainloop()
        finally:
            self.voice_manager.stop_hotkey_monitoring()


def main():
    """Main entry point"""
    app = VoiceInputUI()
    app.run()


if __name__ == "__main__":
    main()