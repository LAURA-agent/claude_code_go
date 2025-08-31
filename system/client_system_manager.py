import os
import subprocess
import json
import asyncio

class ClientSystemManager:
    """
    Minimal system manager for the client.
    Handles local commands: persona, voice, model, and VAD calibration.
    Prints feedback to the console.
    """
    def __init__(self, config_path="personalities.json", vad_settings_path="VAD_settings.json"):
        self.config_path = config_path
        self.vad_settings_path = vad_settings_path

        # Patterns for command detection (make these as robust as you want)
        self.command_patterns = {
            "persona": ["switch to persona", "change persona to", "set persona to"],
            "voice": ["change voice to", "set voice to"],
            "model": ["switch model to", "change model to", "set model to"],
            "vad_calibration": ["calibrate listening", "run calibration", "calibrate vad"],
            "clear_reminder": [
                "i took my medicine", "took my medicine", "medicine taken", "i took it",
                "i'm going to bed", "going to bed", "bedtime", "time for bed",
                "i exercised", "workout done", "finished exercising", "exercise complete",
                "reminder done", "finished that", "task complete", "i did it"
            ],
        }

    def detect_command(self, transcript):
        """
        Detect local commands in the transcript.
        Returns (is_command, command_type, argument).
        """
        text = transcript.lower()
        
        # Special handling for reminder clearing - need to determine reminder type
        if any(phrase in text for phrase in self.command_patterns["clear_reminder"]):
            if any(phrase in text for phrase in ["medicine", "took"]):
                return True, "clear_reminder", "medicine"
            elif any(phrase in text for phrase in ["bed", "bedtime"]):
                return True, "clear_reminder", "bedtime"
            elif any(phrase in text for phrase in ["exercise", "workout"]):
                return True, "clear_reminder", "exercise"
            else:
                return True, "clear_reminder", "general"
        
        # Handle other commands normally
        for cmd_type, patterns in self.command_patterns.items():
            if cmd_type == "clear_reminder":
                continue  # Already handled above
            for pattern in patterns:
                if pattern in text:
                    arg = text.split(pattern, 1)[-1].strip()
                    return True, cmd_type, arg
        return False, None, None

    async def handle_command(self, command_type, argument=None, mcp_session=None, session_id=None):
        """
        Handle the command and print simple console feedback.
        """
        if command_type == "vad_calibration":
            self.run_vad_calibration()
            return True

        if command_type == "persona" and argument:
            self.update_persona(argument)
            return True

        if command_type == "voice" and argument:
            self.update_voice(argument)
            return True

        if command_type == "model" and argument:
            self.update_model(argument)
            return True
            
        if command_type == "clear_reminder" and argument:
            return await self.clear_reminder(argument, mcp_session, session_id)

        print(f"Unknown or unhandled command: {command_type}")
        return False

    async def clear_reminder(self, reminder_type, mcp_session=None, session_id=None):
        """Clear a reminder by calling the server MCP tool"""
        print(f"[INFO] Clearing {reminder_type} reminder...")
        
        if not mcp_session or not session_id:
            print("[WARN] Cannot clear reminder - no MCP session available")
            return False
            
        try:
            response = await mcp_session.call_tool("clear_reminder", arguments={
                "session_id": session_id,
                "reminder_type": reminder_type
            })
            print(f"[INFO] {reminder_type} reminder cleared successfully.")
            return True
        except Exception as e:
            print(f"[WARN] Could not clear {reminder_type} reminder: {e}")
            return False

    async def run_vad_calibration(self, audio_manager=None):
        """Run VAD calibration with proper audio resource coordination"""
        print("Starting VAD calibration...")
        
        # Release audio resources if audio_manager is provided
        if audio_manager:
            await audio_manager.stop_listening()
            await asyncio.sleep(0.2)  # Brief pause for cleanup
        
        # Run calibration subprocess
        process = await asyncio.create_subprocess_exec(
            'python3', 'vad_calib.py',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        # Reinitialize audio if needed
        if audio_manager:
            await audio_manager.initialize_input()
        
        # Process results and display feedback
        if os.path.exists(self.vad_settings_path):
            with open(self.vad_settings_path, "r") as f:
                settings = json.load(f)
            profile = settings.get("profiles", {}).get("current", {})
            print("Calibration complete! New thresholds applied.")
            return True
        return False


    def update_persona(self, persona_name):
        if not os.path.exists(self.config_path):
            print(f"Config file not found: {self.config_path}")
            return
        with open(self.config_path, "r") as f:
            config = json.load(f)
        if "personas" in config and persona_name.lower() in config["personas"]:
            config["active_persona"] = persona_name.lower()
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)
            print(f"Persona switched to: {persona_name}")
        else:
            print(f"Persona '{persona_name}' not found in config.")

    def update_voice(self, voice_name):
        if not os.path.exists(self.config_path):
            print(f"Config file not found: {self.config_path}")
            return
        with open(self.config_path, "r") as f:
            config = json.load(f)
        persona = config.get("active_persona", None)
        if persona and "personas" in config and persona in config["personas"]:
            config["personas"][persona]["voice"] = voice_name
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)
            print(f"Voice switched to: {voice_name} for persona {persona}")
        else:
            print(f"Could not update voice. Persona '{persona}' not found.")

    def update_model(self, model_name):
        if not os.path.exists(self.config_path):
            print(f"Config file not found: {self.config_path}")
            return
        with open(self.config_path, "r") as f:
            config = json.load(f)
        persona = config.get("active_persona", None)
        if persona and "personas" in config and persona in config["personas"]:
            config["personas"][persona]["model"] = model_name
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)
            print(f"Model switched to: {model_name} for persona {persona}")
        else:
            print(f"Could not update model. Persona '{persona}' not found.")
