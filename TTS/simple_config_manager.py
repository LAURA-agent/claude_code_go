#!/usr/bin/env python3
"""
Simple Configuration Manager for Claude-to-Speech
A basic web interface for managing voice settings without Gradio complications
"""

from flask import Flask, render_template_string, request, jsonify
import json
from pathlib import Path

app = Flask(__name__)

# HTML template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Claude-to-Speech Configuration</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .voice-card { border: 1px solid #ddd; padding: 20px; margin: 10px 0; border-radius: 5px; }
        .active { background-color: #e8f4f8; }
        button { padding: 10px 20px; margin: 5px; cursor: pointer; }
        .success { color: green; }
        .error { color: red; }
        select, input { padding: 5px; margin: 5px; }
        textarea { width: 100%; min-height: 60px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎤 Claude-to-Speech Voice Configuration</h1>
        
        <h2>Active Voice</h2>
        <select id="activeVoice" onchange="updateActiveVoice()">
            {% for voice_id, voice_data in voices.items() %}
            <option value="{{ voice_id }}" {% if voice_id == active_voice %}selected{% endif %}>
                {{ voice_data.display_name or voice_data.name }}
            </option>
            {% endfor %}
        </select>
        <button onclick="updateActiveVoice()">Update Active Voice</button>
        <div id="status"></div>
        
        <h2>Voice Details</h2>
        {% for voice_id, voice_data in voices.items() %}
        <div class="voice-card {% if voice_id == active_voice %}active{% endif %}">
            <h3>{{ voice_data.display_name or voice_data.name }}</h3>
            <p><strong>Voice ID:</strong> {{ voice_id }}</p>
            <p><strong>Model:</strong> {{ voice_data.model }}</p>
            <p><strong>Description:</strong><br>{{ voice_data.description }}</p>
        </div>
        {% endfor %}
    </div>
    
    <script>
        function updateActiveVoice() {
            const select = document.getElementById('activeVoice');
            const voiceId = select.value;
            
            fetch('/update_voice', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({voice_id: voiceId})
            })
            .then(response => response.json())
            .then(data => {
                const status = document.getElementById('status');
                status.innerHTML = data.message;
                status.className = data.success ? 'success' : 'error';
                if (data.success) {
                    setTimeout(() => location.reload(), 1000);
                }
            });
        }
    </script>
</body>
</html>
'''

class SimpleConfigManager:
    def __init__(self):
        # Get the directory where this script is located
        script_dir = Path(__file__).parent
        self.config_dir = script_dir / "config"
        self.voices_file = self.config_dir / "voices.json"
        self.load_config()
    
    def load_config(self):
        try:
            print(f"Loading config from: {self.voices_file}")
            with open(self.voices_file, 'r') as f:
                data = json.load(f)
                self.active_voice = data.get("active_voice", "")
                self.voices = data.get("voices", {})
                print(f"Loaded {len(self.voices)} voices")
                print(f"Active voice: {self.active_voice}")
        except Exception as e:
            print(f"Error loading config from {self.voices_file}: {e}")
            self.active_voice = ""
            self.voices = {}
    
    def save_config(self):
        try:
            data = {
                "active_voice": self.active_voice,
                "voices": self.voices
            }
            with open(self.voices_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

config_manager = SimpleConfigManager()

@app.route('/')
def index():
    config_manager.load_config()
    return render_template_string(HTML_TEMPLATE, 
                                voices=config_manager.voices,
                                active_voice=config_manager.active_voice)

@app.route('/update_voice', methods=['POST'])
def update_voice():
    data = request.json
    voice_id = data.get('voice_id')
    
    if voice_id in config_manager.voices:
        config_manager.active_voice = voice_id
        if config_manager.save_config():
            return jsonify({"success": True, "message": f"✅ Active voice updated to {config_manager.voices[voice_id].get('display_name', voice_id)}"})
    
    return jsonify({"success": False, "message": "❌ Failed to update voice"})

if __name__ == '__main__':
    print("Starting Simple Configuration Manager on http://127.0.0.1:5001")
    app.run(host='127.0.0.1', port=5001, debug=False)