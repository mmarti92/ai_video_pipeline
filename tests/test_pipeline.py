"""
Unit tests for the pipeline and video_generator modules.

External dependencies (database, Anthropic, gTTS, moviepy) are all mocked.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# pipeline tests
# ---------------------------------------------------------------------------

class TestRunOnce:
    def test_no_jobs_returns_zero(self):
        import pipeline
        import database
        with patch.object(database, "fetch_pending_jobs", return_value=[]):
            result = pipeline.run_once(batch_size=5)
        assert result == 0

    def test_successful_job_marks_completed(self):
        import pipeline
        import database
        from video_generator import generate_video

        fake_job = {
            "id": "job-uuid-1",
            "stock_symbol": "AAPL",
            "title": "Apple Analysis",
            "description": None,
        }

        with (
            patch.object(database, "fetch_pending_jobs", return_value=[fake_job]),
            patch.object(database, "mark_processing") as mock_processing,
            patch.object(database, "mark_completed") as mock_completed,
            patch.object(database, "mark_failed") as mock_failed,
            patch("pipeline.generate_video", return_value="/output/job-uuid-1.mp4"),
        ):
            result = pipeline.run_once(batch_size=5)

        assert result == 1
        mock_processing.assert_called_once_with("job-uuid-1")
        mock_completed.assert_called_once_with("job-uuid-1", "/output/job-uuid-1.mp4")
        mock_failed.assert_not_called()

    def test_failed_job_marks_failed(self):
        import pipeline
        import database

        fake_job = {
            "id": "job-uuid-2",
            "stock_symbol": "GOOG",
            "title": None,
            "description": None,
        }

        with (
            patch.object(database, "fetch_pending_jobs", return_value=[fake_job]),
            patch.object(database, "mark_processing"),
            patch.object(database, "mark_completed") as mock_completed,
            patch.object(database, "mark_failed") as mock_failed,
            patch("pipeline.generate_video", side_effect=RuntimeError("GPU error")),
        ):
            result = pipeline.run_once(batch_size=5)

        assert result == 0
        mock_completed.assert_not_called()
        mock_failed.assert_called_once()
        args = mock_failed.call_args.args
        assert args[0] == "job-uuid-2"
        assert "GPU error" in args[1]


# ---------------------------------------------------------------------------
# video_generator tests
# ---------------------------------------------------------------------------

class TestTemplateScript:
    def test_contains_symbol(self):
        from video_generator import _template_script
        script = _template_script("MSFT", "Microsoft Weekly", None)
        assert "MSFT" in script
        assert "Microsoft Weekly" in script

    def test_fallback_title(self):
        from video_generator import _template_script
        script = _template_script("AMZN", None, None)
        assert "AMZN" in script


class TestRenderChart:
    def test_creates_png_file(self, tmp_path):
        from video_generator import _render_chart
        chart_path = _render_chart("TSLA", tmp_path, "test-job-id")
        assert Path(chart_path).exists()
        assert chart_path.endswith(".png")


class TestComposeVideo:
    def test_uses_moviepy_v2_api(self, tmp_path):
        """_compose_video must use the moviepy 2.x with_duration/with_audio API."""
        from video_generator import _compose_video
        from unittest.mock import MagicMock, patch, PropertyMock

        mock_audio = MagicMock()
        mock_audio.duration = 5.0

        mock_image = MagicMock()
        mock_image.with_duration.return_value = mock_image
        mock_image.with_audio.return_value = mock_image

        with (
            patch("video_generator.AudioFileClip", return_value=mock_audio),
            patch("video_generator.ImageClip", return_value=mock_image),
        ):
            result = _compose_video(
                str(tmp_path / "chart.png"),
                str(tmp_path / "audio.mp3"),
                tmp_path,
                "job-xyz",
            )

        # with_duration and with_audio (moviepy 2.x) must be called, not set_duration/set_audio
        mock_image.with_duration.assert_called_once_with(5.0)
        mock_image.with_audio.assert_called_once_with(mock_audio)
        mock_image.write_videofile.assert_called_once()
        assert result.endswith("job-xyz.mp4")


class TestGenerateVideo:
    def test_end_to_end_with_mocks(self, tmp_path):
        """Ensure generate_video wires together all sub-steps and returns a path."""
        from video_generator import generate_video

        with (
            patch("video_generator._generate_script", return_value="Test script."),
            patch("video_generator._render_chart", return_value=str(tmp_path / "chart.png")),
            patch("video_generator._synthesise_audio", return_value=str(tmp_path / "audio.mp3")),
            patch("video_generator._compose_video", return_value=str(tmp_path / "out.mp4")),
        ):
            result = generate_video(
                job_id="test-id",
                stock_symbol="NVDA",
                title=None,
                description=None,
                output_dir=str(tmp_path),
            )

        assert result == str(tmp_path / "out.mp4")
