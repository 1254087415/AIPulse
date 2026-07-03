"""Tests for video downloader and transcriber.

Exercises VideoDownloader.download path handling and AudioTranscriber.transcribe output.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from aipulse.video.downloader import VideoDownloader
from aipulse.video.transcriber import AudioTranscriber


async def test_downloader_creates_work_dir(tmp_path):
    downloader = VideoDownloader(tmp_path)

    with patch("aipulse.video.downloader.yt_dlp.YoutubeDL") as mock_ydl:
        instance = mock_ydl.return_value.__enter__.return_value
        instance.extract_info.return_value = {"title": "Test"}
        instance.prepare_filename.return_value = str(tmp_path / "task_1" / "Test.mp4")
        result = await downloader.download("https://youtube.com/watch", "task_1")

    assert result["work_dir"] == tmp_path / "task_1"
    assert (tmp_path / "task_1").exists()


async def test_downloader_uses_bestaudio(tmp_path):
    downloader = VideoDownloader(tmp_path)

    with patch("aipulse.video.downloader.yt_dlp.YoutubeDL") as mock_ydl:
        instance = mock_ydl.return_value.__enter__.return_value
        instance.extract_info.return_value = {"title": "Test"}
        instance.prepare_filename.return_value = str(tmp_path / "task_1" / "Test.webm")
        await downloader.download("https://youtube.com/watch", "task_1")

        opts = mock_ydl.call_args[0][0]
        assert opts["format"] == "bestaudio/best"


async def test_transcriber_lazy_loads_model():
    transcriber = AudioTranscriber(model_size="tiny")
    assert transcriber._model is None

    with patch("aipulse.video.transcriber.WhisperModel") as mock_model:
        mock_model.return_value.transcribe.return_value = (
            [MagicMock(text=" hello "), MagicMock(text="world")],
            None,
        )
        result = await transcriber.transcribe(Path("/tmp/audio.mp3"))

    assert result == "hello world"
    mock_model.assert_called_once_with("tiny", device="cpu", compute_type="int8")


async def test_transcriber_reuses_model():
    transcriber = AudioTranscriber(model_size="tiny")
    with patch("aipulse.video.transcriber.WhisperModel") as mock_model:
        mock_model.return_value.transcribe.return_value = ([MagicMock(text="a")], None)
        await transcriber.transcribe(Path("/tmp/audio.mp3"))
        await transcriber.transcribe(Path("/tmp/audio.mp3"))
    assert mock_model.call_count == 1
