"""Whisper ASR subtitle fallback strategy."""

import logging
from pathlib import Path

from aipulse.video.parsers.base import ParsedContent
from aipulse.video.subtitle.base import SubtitleResult, SubtitleStrategy
from aipulse.video.transcriber import AudioTranscriber

logger = logging.getLogger(__name__)


class WhisperSubtitleStrategy(SubtitleStrategy):
    """Transcribe audio locally with faster-whisper."""

    def __init__(self, model_size: str = "small"):
        self._transcriber = AudioTranscriber(model_size=model_size)

    async def is_available(self, content: ParsedContent) -> bool:
        return content.audio_path is not None or content.video_path is not None

    async def fetch(self, content: ParsedContent, work_dir: Path) -> SubtitleResult:
        audio_path = content.audio_path or content.video_path
        if audio_path is None:
            return SubtitleResult(text=None, source="whisper")

        try:
            text = await self._transcriber.transcribe(audio_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Whisper transcription failed: %s", exc)
            return SubtitleResult(text=None, source="whisper")

        return SubtitleResult(text=text, source="whisper")
