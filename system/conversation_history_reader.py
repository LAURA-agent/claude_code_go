#!/usr/bin/env python3

import json
import os
import re
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import time


class ConversationMessage:
    """Represents a single conversation message"""
    
    def __init__(self, role: str, content: str, timestamp: str, mood: Optional[str] = None):
        self.role = role  # 'user' or 'assistant'
        self.content = content
        self.timestamp = timestamp
        self.mood = mood
        self.datetime = self._parse_timestamp(timestamp)
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime object"""
        try:
            # Handle various timestamp formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ", 
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f"
            ]:
                try:
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    continue
            
            # Fallback to current time if parsing fails
            print(f"[ConversationHistoryReader] Warning: Could not parse timestamp: {timestamp_str}")
            return datetime.now()
            
        except Exception as e:
            print(f"[ConversationHistoryReader] Error parsing timestamp {timestamp_str}: {e}")
            return datetime.now()
    
    def get_relative_time(self) -> str:
        """Get human-readable relative time string"""
        now = datetime.now()
        diff = now - self.datetime
        
        if diff.total_seconds() < 60:
            return "just now"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = diff.days
            return f"{days} day{'s' if days != 1 else ''} ago"
    
    def get_display_content(self) -> str:
        """Get content formatted for display (handle mood indicators)"""
        # Remove mood indicators in brackets like [thoughtful], [confused]
        content = re.sub(r'\[[\w\s]+\]', '', self.content).strip()
        
        # Limit length for display
        if len(content) > 150:
            content = content[:147] + "..."
        
        return content
    
    def extract_mood(self) -> Optional[str]:
        """Extract mood from content if present"""
        if not self.mood:
            # Look for mood indicators in brackets
            mood_match = re.search(r'\[(\w+)\]', self.content)
            if mood_match:
                return mood_match.group(1)
        return self.mood


class ChatLogFileHandler(FileSystemEventHandler):
    """File system event handler for monitoring chat log changes"""
    
    def __init__(self, callback: Callable):
        self.callback = callback
        
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            # Debounce rapid file changes
            time.sleep(0.1)
            self.callback(event.src_path)


class ConversationHistoryReader:
    """
    Reads and manages conversation history from chat log files.
    Provides real-time monitoring and formatting for Gradio display.
    """
    
    def __init__(self, chat_logs_dir: str = "/home/user/rp_client/chat_logs"):
        self.chat_logs_dir = Path(chat_logs_dir)
        self.messages: List[ConversationMessage] = []
        self.observer: Optional[Observer] = None
        self.update_callback: Optional[Callable] = None
        self.max_messages = 100  # Limit displayed messages for performance
        
        print(f"[ConversationHistoryReader] Initializing with directory: {self.chat_logs_dir}")
        
        # Ensure chat logs directory exists
        self.chat_logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Load initial conversation history
        self.load_all_messages()
    
    def set_update_callback(self, callback: Callable):
        """Set callback function to notify Gradio of updates"""
        self.update_callback = callback
    
    def load_all_messages(self):
        """Load all conversation messages from existing log files"""
        print("[ConversationHistoryReader] Loading conversation history...")
        
        self.messages.clear()
        
        # Get all JSON files sorted by date (newest first)
        log_files = sorted(
            self.chat_logs_dir.glob("chat_log_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        
        # Load messages from recent files (limit to prevent performance issues)
        files_loaded = 0
        for log_file in log_files:
            if files_loaded >= 7:  # Load last 7 days max
                break
                
            try:
                messages_from_file = self._load_messages_from_file(log_file)
                self.messages.extend(messages_from_file)
                files_loaded += 1
                
            except Exception as e:
                print(f"[ConversationHistoryReader] Error loading {log_file}: {e}")
        
        # Sort all messages by timestamp (newest first)
        self.messages.sort(key=lambda m: m.datetime, reverse=True)
        
        # Limit to max messages
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[:self.max_messages]
        
        print(f"[ConversationHistoryReader] Loaded {len(self.messages)} messages from {files_loaded} files")
    
    def _load_messages_from_file(self, file_path: Path) -> List[ConversationMessage]:
        """Load messages from a single chat log file"""
        messages = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both list format and object format
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'role' in item and 'content' in item:
                        message = ConversationMessage(
                            role=item['role'],
                            content=item['content'],
                            timestamp=item.get('timestamp', ''),
                            mood=item.get('mood')
                        )
                        messages.append(message)
            
        except json.JSONDecodeError as e:
            print(f"[ConversationHistoryReader] JSON decode error in {file_path}: {e}")
        except Exception as e:
            print(f"[ConversationHistoryReader] Error reading {file_path}: {e}")
        
        return messages
    
    def start_monitoring(self):
        """Start monitoring chat log directory for changes"""
        if self.observer is not None:
            print("[ConversationHistoryReader] Already monitoring")
            return
        
        print("[ConversationHistoryReader] Starting file monitoring...")
        
        try:
            self.observer = Observer()
            event_handler = ChatLogFileHandler(self._on_file_changed)
            self.observer.schedule(event_handler, str(self.chat_logs_dir), recursive=False)
            self.observer.start()
            print("[ConversationHistoryReader] File monitoring started")
            
        except Exception as e:
            print(f"[ConversationHistoryReader] Error starting file monitoring: {e}")
    
    def stop_monitoring(self):
        """Stop monitoring chat log directory"""
        if self.observer is not None:
            print("[ConversationHistoryReader] Stopping file monitoring...")
            self.observer.stop()
            self.observer.join()
            self.observer = None
            print("[ConversationHistoryReader] File monitoring stopped")
    
    def _on_file_changed(self, file_path: str):
        """Handle file change events"""
        try:
            print(f"[ConversationHistoryReader] File changed: {file_path}")
            
            # Reload messages from changed file
            changed_file = Path(file_path)
            if changed_file.suffix == '.json' and 'chat_log_' in changed_file.name:
                
                # Load new messages from the changed file
                new_messages = self._load_messages_from_file(changed_file)
                
                if new_messages:
                    # Add new messages to the beginning of the list
                    # Remove duplicates by timestamp and content
                    existing_timestamps = {(m.timestamp, m.content) for m in self.messages}
                    unique_new_messages = [
                        m for m in new_messages 
                        if (m.timestamp, m.content) not in existing_timestamps
                    ]
                    
                    if unique_new_messages:
                        self.messages = unique_new_messages + self.messages
                        
                        # Limit total messages
                        if len(self.messages) > self.max_messages:
                            self.messages = self.messages[:self.max_messages]
                        
                        print(f"[ConversationHistoryReader] Added {len(unique_new_messages)} new messages")
                        
                        # Notify Gradio of update
                        if self.update_callback:
                            self.update_callback()
            
        except Exception as e:
            print(f"[ConversationHistoryReader] Error handling file change: {e}")
    
    def get_messages_for_display(self, limit: int = 50) -> List[Dict]:
        """Get formatted messages for Gradio display"""
        display_messages = []
        
        for message in self.messages[:limit]:
            # Format message for display
            display_msg = {
                'role': message.role,
                'content': message.get_display_content(),
                'time': message.get_relative_time(),
                'timestamp': message.timestamp,
                'mood': message.extract_mood() or 'casual',
                'datetime': message.datetime.isoformat()
            }
            display_messages.append(display_msg)
        
        return display_messages
    
    def get_formatted_chat_html(self, limit: int = 50) -> str:
        """Get conversation history formatted as HTML for Gradio display"""
        html_parts = ['<div style="max-height: 600px; overflow-y: auto; padding: 10px;">']
        
        messages = self.get_messages_for_display(limit)
        
        for msg in reversed(messages):  # Show oldest first in display
            role_class = "user-message" if msg['role'] == 'user' else "assistant-message"
            role_label = "You" if msg['role'] == 'user' else "LAURA"
            
            # Choose colors based on role
            if msg['role'] == 'user':
                bg_color = "#e3f2fd"  # Light blue
                text_color = "#1976d2"  # Blue
                align = "flex-end"
                margin = "margin-left: 20%;"
            else:
                bg_color = "#f1f8e9"  # Light green
                text_color = "#388e3c"  # Green
                align = "flex-start" 
                margin = "margin-right: 20%;"
            
            mood_indicator = ""
            if msg['role'] == 'assistant' and msg['mood'] != 'casual':
                mood_indicator = f'<small style="color: #666; font-style: italic;">[{msg["mood"]}]</small><br>'
            
            html_parts.append(f'''
            <div style="display: flex; justify-content: {align}; margin-bottom: 15px;">
                <div style="
                    background-color: {bg_color}; 
                    border-radius: 10px; 
                    padding: 12px; 
                    {margin}
                    border-left: 4px solid {text_color};
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <div style="font-weight: bold; color: {text_color}; margin-bottom: 5px;">
                        {role_label}
                    </div>
                    {mood_indicator}
                    <div style="color: #333; line-height: 1.4;">
                        {msg['content']}
                    </div>
                    <div style="font-size: 11px; color: #666; margin-top: 8px; text-align: right;">
                        {msg['time']}
                    </div>
                </div>
            </div>
            ''')
        
        html_parts.append('</div>')
        
        return ''.join(html_parts)
    
    def get_today_message_count(self) -> Dict[str, int]:
        """Get message counts for today"""
        today = date.today()
        user_count = 0
        assistant_count = 0
        
        for message in self.messages:
            if message.datetime.date() == today:
                if message.role == 'user':
                    user_count += 1
                else:
                    assistant_count += 1
        
        return {
            'user_messages': user_count,
            'assistant_messages': assistant_count,
            'total_messages': user_count + assistant_count
        }
    
    def search_messages(self, query: str, limit: int = 20) -> List[Dict]:
        """Search for messages containing the query string"""
        if not query.strip():
            return []
        
        query_lower = query.lower()
        matching_messages = []
        
        for message in self.messages:
            if query_lower in message.content.lower():
                display_msg = {
                    'role': message.role,
                    'content': message.get_display_content(),
                    'time': message.get_relative_time(),
                    'timestamp': message.timestamp,
                    'mood': message.extract_mood() or 'casual'
                }
                matching_messages.append(display_msg)
                
                if len(matching_messages) >= limit:
                    break
        
        return matching_messages
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_monitoring()
        print("[ConversationHistoryReader] Cleanup completed")