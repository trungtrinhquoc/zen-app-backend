"""
Voice API Endpoints
Handles voice transcription (STT only, no storage)
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.modules.voice.stt_service import STTService
from app.utils.logger import logger
from pydantic import BaseModel


router = APIRouter()


class TranscribeResponse(BaseModel):
    text: str
    language: str
    duration: float


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribeVoice(
    file: UploadFile = File(...)
):
    """
    Transcribe voice to text (audio is NOT stored)
    
    Flow:
    1. Receive audio from frontend
    2. Transcribe with Groq Whisper
    3. Return text immediately
    4. Audio is discarded (not saved)
    
    Example:
        curl -X POST http://localhost:8000/api/v1/voice/transcribe \
             -F "file=@voice.webm"
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Must be audio file."
            )
        
        # Read audio data
        audioData = await file.read()
        
        logger.info(
            f"📥 Voice upload: {file.filename}, "
            f"{len(audioData)} bytes, "
            f"type: {file.content_type}"
        )
        
        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(audioData) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {max_size / 1024 / 1024}MB"
            )
        
        # Transcribe (audio will be deleted after)
        sttService = STTService()
        result = await sttService.transcribe(
            audioData=audioData,
            filename=file.filename or "audio.webm"
        )
        
        logger.info(f"✅ Transcription successful: '{result['text'][:50]}...'")
        
        return TranscribeResponse(
            text=result["text"],
            language=result["language"],
            duration=result["duration"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        logger.error(f"❌ Transcription endpoint fatal error: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )
