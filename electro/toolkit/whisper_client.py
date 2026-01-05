"""Whisper client utility for audio transcription."""

import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile
from openai import AsyncOpenAI

from settings import settings

from electro.toolkit.loguru_logging import logger


class WhisperTranscriptionError(Exception):
    """Custom exception for Whisper transcription errors."""

    pass


async def validate_audio_file(file: UploadFile) -> None:
    """
    Validate the uploaded audio file.
    
    Args:
        file: The uploaded file to validate
        
    Raises:
        HTTPException: If file validation fails
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    file_extension = Path(file.filename).suffix.lower().lstrip('.')
    if file_extension not in settings.SUPPORTED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format. Supported formats: {', '.join(settings.SUPPORTED_AUDIO_FORMATS)}"
        )
    
    if file.size and file.size > settings.MAX_AUDIO_FILE_SIZE:
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Maximum size: {settings.MAX_AUDIO_FILE_SIZE // (1024 * 1024)}MB"
        )


async def transcribe_audio(
    file: UploadFile,
    language: Optional[str] = None,
    response_format: str = "json",
    temperature: float = 0.0
) -> dict:
    """
    Transcribe audio file using OpenAI Whisper.
    
    Args:
        file: Audio file to transcribe
        language: Optional language code (e.g., 'en', 'es', 'fr')
        response_format: Response format ('json', 'text', 'srt', 'verbose_json', 'vtt')
        temperature: Sampling temperature between 0 and 1
        
    Returns:
        Dictionary containing transcription result
        
    Raises:
        WhisperTranscriptionError: If transcription fails
    """
    await validate_audio_file(file)
    
    client = AsyncOpenAI(
        base_url=settings.OPENAI_API_BASE_URL,
        api_key=settings.OPENAI_API_KEY
    )
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{Path(file.filename).suffix}") as temp_file:
        try:
            # Write uploaded file to temporary file
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            
            # Transcribe using OpenAI Whisper
            with open(temp_file.name, 'rb') as audio_file:
                transcription_params = {
                    "file": audio_file,
                    "model": settings.OPENAI_WHISPER_MODEL,
                    "response_format": response_format,
                    "temperature": temperature
                }
                
                if language:
                    transcription_params["language"] = language
                
                logger.info(f"Starting transcription for file: {file.filename}")
                transcript = await client.audio.transcriptions.create(**transcription_params)
                logger.info(f"Transcription completed for file: {file.filename}")
                
                # Handle different response formats
                if response_format == "json":
                    return {
                        "text": transcript.text,
                        "language": getattr(transcript, 'language', None),
                        "duration": getattr(transcript, 'duration', None),
                        "filename": file.filename
                    }
                elif response_format == "verbose_json":
                    return {
                        "text": transcript.text,
                        "language": getattr(transcript, 'language', None),
                        "duration": getattr(transcript, 'duration', None),
                        "segments": getattr(transcript, 'segments', []),
                        "filename": file.filename
                    }
                else:
                    return {
                        "text": str(transcript),
                        "filename": file.filename
                    }
                    
        except Exception as e:
            logger.error(f"Transcription failed for file {file.filename}: {str(e)}")
            raise WhisperTranscriptionError(f"Transcription failed: {str(e)}")
        
        finally:
            # Clean up temporary file
            try:
                Path(temp_file.name).unlink(missing_ok=True)
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temporary file: {cleanup_error}")