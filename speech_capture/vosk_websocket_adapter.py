#!/usr/bin/env python3
"""
VOSK WebSocket Adapter
Provides compatibility layer between VoskWebSocketClient and speech_processor expectations
"""

from speech_capture.vosk_websocket_client import VoskWebSocketClient
from typing import Tuple, Optional


class VoskWebSocketAdapter(VoskWebSocketClient):
    """
    Adapter that wraps VoskWebSocketClient to match the interface expected by speech_processor.
    
    The speech_processor expects: (is_final, confidence_score, partial_text)
    But VoskWebSocketClient returns: (is_final, is_speech_in_frame, current_full_text)
    """
    
    def __init__(self, server_url: str = "ws://localhost:2700", sample_rate: int = 16000):
        super().__init__(server_url, sample_rate)
        self.last_confidence = None
        
    def process_frame(self, frame_data_bytes: bytes) -> Tuple[bool, Optional[float], str]:
        """
        Process audio frame and return transcription results in expected format
        
        Returns:
            Tuple of (is_final_chunk_result, confidence_score, current_text)
        """
        # Get the original response
        is_final, is_speech, current_text = super().process_frame(frame_data_bytes)
        
        # For now, we'll use None for confidence_score since extracting it
        # from the queue was interfering with get_final_text()
        confidence_score = None
        
        # Return in expected format
        return is_final, confidence_score, current_text


def VoskTranscriber(model_path: str = None, sample_rate: int = 16000, server_url: str = "ws://localhost:2700"):
    """
    Drop-in replacement for original VoskTranscriber that returns the adapted client
    """
    return VoskWebSocketAdapter(server_url=server_url, sample_rate=sample_rate)