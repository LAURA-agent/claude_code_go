import asyncio
import os
from pathlib import Path
import traceback
import httpx # For Cartesia and ElevenLabs direct API calls

# Import secrets if Cartesia or ElevenLabs keys are stored there
try:
    from config.client_secret import ELEVENLABS_API_KEY, CARTESIA_API_KEY
except ImportError:
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
    if not ELEVENLABS_API_KEY:
        print("[TTS WARN] ELEVENLABS_API_KEY not found in client_secret.py or environment variables.")
    if not CARTESIA_API_KEY:
        print("[TTS WARN] CARTESIA_API_KEY not found in client_secret.py or environment variables.")

# Assuming client_config is in the same directory or PYTHON_PATH is set
from config.client_config import client_settings, get_voice_params_for_persona, DEFAULT_PIPER_MODEL_PATH


class TTSHandler:
    def __init__(self):
        self.elevenlabs_api_key = ELEVENLABS_API_KEY
        self.cartesia_api_key = CARTESIA_API_KEY
        self.piper_process = None # For managing the Piper subprocess

    def get_active_provider_for_tts_attempt(self) -> str | None:
        """Determines the TTS provider to attempt based on current settings."""
        current_tts_mode = client_settings.get("tts_mode", "api") # Default to api if not set
        if current_tts_mode == "api":
            return client_settings.get("api_tts_provider", "elevenlabs") # Default to elevenlabs if provider not set
        elif current_tts_mode == "local":
            return "piper"
        elif current_tts_mode == "text":
            return "text_only" # Special case for no TTS
        print(f"[TTS WARN] Unknown TTS mode: {current_tts_mode}")
        return None # Should not happen if config is validated

    def get_fallback_provider(self, attempted_provider: str) -> str | None:
        """Determines a fallback TTS provider."""
        if attempted_provider == "piper": # If local fails, try preferred API
            api_provider = client_settings.get("api_tts_provider")
            if api_provider in ["elevenlabs", "cartesia"]: return api_provider
        elif attempted_provider == "cartesia": # If Cartesia fails, try ElevenLabs
             if self.elevenlabs_api_key: return "elevenlabs"
        elif attempted_provider == "elevenlabs": # If ElevenLabs fails, try Cartesia
            if self.cartesia_api_key: return "cartesia"
        
        # If primary API provider failed, and local is an option, could try local as last resort
        # For now, simple one-step fallback primarily from local to API, or between APIs.
        return None

    async def generate_audio(self, text: str, persona_name: str | None) -> tuple[bytes | None, str | None]:
        if not text:
            print("[TTS WARN] generate_audio called with empty text.")
            return None, None

        primary_provider = self.get_active_provider_for_tts_attempt()
        if primary_provider == "text_only":
            print("[TTS INFO] Text-only mode. Skipping TTS generation.")
            return None, "text_only"
        if not primary_provider:
            print("[TTS ERROR] Could not determine primary TTS provider.")
            return None, None

        audio_bytes, engine_used = await self._try_generate(text, primary_provider, persona_name)

        if not audio_bytes:
            print(f"[TTS INFO] Primary TTS with {primary_provider} failed.")
            fallback_provider = self.get_fallback_provider(primary_provider)
            if fallback_provider:
                print(f"[TTS INFO] Attempting fallback with {fallback_provider}.")
                audio_bytes, engine_used = await self._try_generate(text, fallback_provider, persona_name)
                if not audio_bytes:
                    print(f"[TTS ERROR] Fallback TTS with {fallback_provider} also failed.")
            else:
                print("[TTS INFO] No fallback provider available or configured.")
        
        if engine_used:
            print(f"[TTS INFO] Audio generated successfully with {engine_used}.")
        return audio_bytes, engine_used

    async def _try_generate(self, text: str, provider_name: str, persona_name: str | None) -> tuple[bytes | None, str | None]:
        """Attempts to generate audio using the specified provider and persona."""
        voice_params = get_voice_params_for_persona(provider_name, persona_name)
        if not voice_params or not any(voice_params.values()): # Check if params dict is empty or all values are None
            print(f"[TTS ERROR] No valid voice parameters found for provider '{provider_name}' and persona '{persona_name}'. Cannot generate audio.")
            return None, None
        
        print(f"[TTS ATTEMPT] Provider: {provider_name}, Persona: {persona_name}, Params: {voice_params}")

        audio_bytes = None
        if provider_name == "elevenlabs":
            audio_bytes = await self._generate_elevenlabs(text, voice_params)
        elif provider_name == "cartesia":
            audio_bytes = await self._generate_cartesia(text, voice_params)
        elif provider_name == "piper":
            audio_bytes = await self._generate_piper(text, voice_params)
        
        return audio_bytes, provider_name if audio_bytes else None

    async def _generate_elevenlabs(self, text: str, voice_params: dict) -> bytes | None:
        if not self.elevenlabs_api_key:
            print("[TTS ERROR] ElevenLabs API key not available.")
            return None
       
        voice_name_or_id = voice_params.get("voice_name_or_id")
        model = voice_params.get("model")
        if not voice_name_or_id or not model:
            print(f"[TTS ERROR] Missing voice_name_or_id or model for ElevenLabs. Params: {voice_params}")
            return None
       
        try:
            print(f"[TTS INFO] Requesting ElevenLabs: Voice='{voice_name_or_id}', Model='{model}'")
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_name_or_id}"
            headers = {
                "xi-api-key": self.elevenlabs_api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "text": text,
                "model_id": model
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    print(f"[TTS ERROR] ElevenLabs API returned status {response.status_code}: {response.text}")
                    return None
                
                audio_data = response.content
                if not audio_data:
                    print("[TTS WARN] ElevenLabs returned no audio data.")
                    return None
                    
                return audio_data
                
        except Exception as e:
            print(f"[TTS ERROR] ElevenLabs API error: {e}")
            traceback.print_exc()
            return None

    async def _generate_cartesia(self, text: str, voice_params: dict) -> bytes | None:
        if not self.cartesia_api_key:
            print("[TTS ERROR] Cartesia API key not available.")
            return None

        voice_id = voice_params.get("voice_id")
        model_id = voice_params.get("model", "sonic-en")
        
        if not voice_id:
            print(f"[TTS ERROR] Missing voice_id for Cartesia. Params: {voice_params}")
            return None
        
        try:
            print(f"[TTS INFO] Requesting Cartesia: VoiceID='{voice_id}', Model='{model_id}'")
            
            # Try using Cartesia Python SDK first
            try:
                from cartesia import Cartesia
                
                client = Cartesia(api_key=self.cartesia_api_key)
                
                # Generate audio
                response = client.tts.bytes(
                    model_id=model_id,
                    transcript=text,
                    voice={
                        "id": voice_id
                    },
                    output_format="mp3_22050_32"
                )
                
                if not response:
                    print("[TTS WARN] Cartesia returned no audio data.")
                    return None
                    
                return response
                
            except ImportError:
                print("[TTS INFO] Cartesia SDK not available, falling back to direct API call")
                
                # Fallback to direct API call
                url = "https://api.cartesia.ai/tts/bytes"
                headers = {
                    "X-API-Key": self.cartesia_api_key,
                    "Cartesia-Version": "2025-04-16",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model_id": model_id,
                    "transcript": text,
                    "voice": {"id": voice_id},
                    "output_format": "mp3_22050_32"
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=payload)
                    
                    if response.status_code != 200:
                        print(f"[TTS ERROR] Cartesia API returned status {response.status_code}: {response.text}")
                        return None
                    
                    audio_data = response.content
                    if not audio_data:
                        print("[TTS WARN] Cartesia returned no audio data.")
                        return None
                        
                    return audio_data
            
        except Exception as e:
            print(f"[TTS ERROR] Cartesia request failed: {e}")
            traceback.print_exc()
            return None

    async def _generate_piper(self, text: str, voice_params: dict) -> bytes | None:
        piper_model_path = voice_params.get("model_path", DEFAULT_PIPER_MODEL_PATH)
        # Piper voice name/speaker ID from config is for the --speaker flag if model is multi-speaker
        # If the model file itself implies the voice (e.g. en_US-amy-low.onnx), this might be None
        piper_speaker_id_str = voice_params.get("voice_name") # This should be a speaker ID (number as string) for --speaker

        if not Path(piper_model_path).exists():
            print(f"[TTS ERROR] Piper model not found: {piper_model_path}")
            return None
        
        command = ["piper", "--model", str(piper_model_path), "--output-raw"]
        if piper_speaker_id_str: # Only add --speaker if a speaker ID is provided
            try:
                int(piper_speaker_id_str) # Validate it's a number-like string for speaker ID
                command.extend(["--speaker", piper_speaker_id_str])
            except ValueError:
                print(f"[TTS WARN] Piper voice_name '{piper_speaker_id_str}' is not a valid speaker ID. Omitting --speaker flag.")
        
        print(f"[TTS INFO] Requesting Piper: Model='{piper_model_path}', Speaker ID='{piper_speaker_id_str if piper_speaker_id_str else 'Default (0 or single speaker model)'}'")
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout_bytes, stderr_bytes = await process.communicate(input=text.encode('utf-8'))

        if process.returncode != 0:
            print(f"[TTS ERROR] Piper failed (Code {process.returncode}): {stderr_bytes.decode()}")
            return None
        
        if not stdout_bytes:
            print("[TTS WARN] Piper produced no audio data.")
            return None
            
        # Convert raw PCM S16LE bytes to a proper WAV file in memory
        # Typical Piper output (check model's config.json): 1 channel, 22050 Hz, 16-bit S16LE
        # These parameters might need to be configurable or read from model's config if they vary
        sample_rate = 22050 # Get this from Piper model's config.json if possible
        channels = 1
        sampwidth = 2 # S16LE = 2 bytes

        import wave
        import io

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(sample_rate)
            wf.writeframes(stdout_bytes)
        
        wav_bytes_with_header = wav_buffer.getvalue()
        print(f"[TTS INFO] Piper generated {len(stdout_bytes)} raw bytes, converted to {len(wav_bytes_with_header)} WAV bytes.")
        return wav_bytes_with_header
