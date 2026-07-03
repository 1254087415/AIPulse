"""Audio transcriber using faster-whisper."""

from pathlib import Path

from faster_whisper import WhisperModel


class AudioTranscriber:
    """Transcribe audio files to text with faster-whisper."""

    def __init__(self, model_size: str = "small"):
        self.model_size = model_size
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    async def transcribe(self, audio_path: Path) -> str:
        """Transcribe an audio file and return plain text."""
        segments, _ = self._get_model().transcribe(str(audio_path))
        return " ".join(segment.text.strip() for segment in segments)
