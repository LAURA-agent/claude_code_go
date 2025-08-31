#!/usr/bin/env python3
"""
Simple Apple Watch Text Injection Server
Receives text via HTTP and injects it using virtual keyboard
"""

from flask import Flask, request, jsonify
from standalone_injector import StandaloneInjector
from evdev import UInput
import time

app = Flask(__name__)
injector = StandaloneInjector()

@app.route('/watch/message', methods=['POST'])
def handle_watch_message():
    """Receive text from Apple Watch and inject it"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Missing 'text' field"}), 400
            
        text = data['text']
        print(f"[APPLE_WATCH] Received: '{text}'")
        
        # Inject the text using virtual keyboard
        try:
            with UInput(injector.capabilities, name='apple-watch-injector', version=0x3) as ui:
                time.sleep(0.2)  # Let system recognize the device
                injector.type_text(ui, text)
                print(f"[APPLE_WATCH] Successfully injected text")
                return jsonify({"status": "success", "message": "Text injected"}), 200
        except Exception as e:
            print(f"[APPLE_WATCH] Injection failed: {e}")
            return jsonify({"error": f"Injection failed: {str(e)}"}), 500
            
    except Exception as e:
        print(f"[APPLE_WATCH] Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    """Health check endpoint"""
    return jsonify({"status": "running", "service": "Apple Watch Text Injector"}), 200

@app.route('/tts/speak', methods=['POST'])
def handle_tts():
    """TTS endpoint using the new speak.py"""
    try:
        import subprocess
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Missing 'text' field"}), 400
            
        text = data['text']
        result = subprocess.run([
            'python3', '/home/user/rp_client/TTS/speak.py', text
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({"status": "success", "message": "TTS played"}), 200
        else:
            return jsonify({"error": "TTS failed"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🍎 Apple Watch Text Injection Server")
    print("=====================================")
    print("Endpoints:")
    print("  POST /watch/message - Inject text from Apple Watch")
    print("  POST /tts/speak    - Play text via TTS")
    print("  GET  /status       - Health check")
    print("\nStarting server on port 8080...")
    print("Your IP: Check network icon in system tray")
    
    app.run(host='0.0.0.0', port=8080, debug=False)