"""
Speech-to-Text Service
Uses Google Cloud Speech-to-Text (60 min/month Free Tier)
"""
from google.cloud import speech
from google.oauth2 import service_account
from app.core.config import settings
from app.utils.logger import logger
import os
from typing import Dict


class STTService:
    """Speech-to-Text using Google Cloud STT API"""
    
    def __init__(self):
        credentials_path = getattr(settings, 'GOOGLE_APPLICATION_CREDENTIALS', None)
        
        try:
            if credentials_path and os.path.exists(credentials_path):
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path
                )
                self.client = speech.SpeechClient(credentials=credentials)
                #logger.info(f"✅ Google STT initialized with credentials: {credentials_path}")
            else:
                # Fallback to Application Default Credentials (ADC)
                self.client = speech.SpeechClient()
                logger.warning("🔑 Google STT using Default Credentials (ADC)")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google STT client: {e}")
            raise ValueError(f"Google Cloud credentials missing or invalid: {str(e)}")

    async def transcribe(
        self,
        audioData: bytes,
        filename: str = "audio.webm"
    ) -> Dict[str, any]:
        """
        Transcribe audio to text using Google Cloud STT  
        Returns:
            {
                "text": "Tôi cảm thấy buồn hôm nay",
                "language": "vi-VN",
                "duration": 0.0
            }
        """
        try:
            logger.info(f"🎤 Transcribing audio with Google STT: {len(audioData)} bytes")
            
            audio = speech.RecognitionAudio(content=audioData)
            
            config = speech.RecognitionConfig(
                language_code=settings.STT_LANGUAGE,  
                enable_automatic_punctuation=True,
            )
            
            #logger.info(f"📡 Calling Google STT API...")
            response = self.client.recognize(config=config, audio=audio)
            #logger.info(f"✅ Google STT response received: {len(response.results)} results")
            
            transcript_parts = []
            for result in response.results:
                transcript_parts.append(result.alternatives[0].transcript)
            
            text = " ".join(transcript_parts).strip()
            confidence = sum([r.alternatives[0].confidence for r in response.results]) / len(response.results) if response.results else 0.0
            
            if not text:
                logger.warning(f"⚠️ Google STT returned empty transcript. Results count: {len(response.results)}")
                logger.warning(f"⚠️ Audio size: {len(audioData)} bytes, Language: {settings.STT_LANGUAGE}")
                return {
                    "text": "",
                    "language": settings.STT_LANGUAGE,
                    "duration": 0.0,
                    "confidence": 0.0
                }
            
            logger.info(f"✅ Transcription: '{text}' (Confidence: {confidence:.2f})")
            
            return {
                "text": text,
                "language": settings.STT_LANGUAGE,
                "duration": 0.0,
                "confidence": float(confidence)
            }
            
        except Exception as e:
            logger.error(f"❌ Google STT Transcription failed: {e}")
            
            # If default config fails, try a fallback with minimal config
            if "vi-VN" not in str(e): 
                #logger.info("🔄 Retrying with minimalist config...")
                try:
                    minimal_config = speech.RecognitionConfig(
                        language_code=settings.STT_LANGUAGE,
                    )
                    response = self.client.recognize(config=minimal_config, audio=audio)
                    text = " ".join([r.alternatives[0].transcript for r in response.results]).strip()
                    return {
                        "text": text,
                        "language": settings.STT_LANGUAGE,
                        "duration": 0.0,
                        "confidence": 0.99 
                    }
                except Exception as e2:
                    logger.error(f"❌ Fallback also failed: {e2}")
            
            raise Exception(f"Google STT error: {str(e)}")
