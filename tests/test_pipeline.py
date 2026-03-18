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
            patch.object(database, "fetch_forecasts", return_value=[]),
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
            patch.object(database, "fetch_forecasts", return_value=[]),
            patch("pipeline.generate_video", side_effect=RuntimeError("GPU error")),
        ):
            result = pipeline.run_once(batch_size=5)

        assert result == 0
        mock_completed.assert_not_called()
        mock_failed.assert_called_once()
        args = mock_failed.call_args.args
        assert args[0] == "job-uuid-2"
        assert "GPU error" in args[1]

    def test_forecasts_passed_to_generate_video(self):
        """Pipeline must pass fetched forecasts to generate_video()."""
        import pipeline
        import database

        fake_job = {
            "id": "job-uuid-3",
            "stock_symbol": "NVDA",
            "title": "NVIDIA",
            "description": None,
        }
        fake_forecasts = [{"current_price": 875.50, "predicted_price": 940.50}]

        with (
            patch.object(database, "fetch_pending_jobs", return_value=[fake_job]),
            patch.object(database, "mark_processing"),
            patch.object(database, "mark_completed"),
            patch.object(database, "fetch_forecasts", return_value=fake_forecasts),
            patch("pipeline.generate_video", return_value="/output/job.mp4") as mock_gen,
        ):
            pipeline.run_once(batch_size=5)

        mock_gen.assert_called_once()
        assert mock_gen.call_args.kwargs["forecasts"] == fake_forecasts


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

    def test_with_forecasts(self):
        from video_generator import _template_script
        forecasts = [{
            "forecast_date": "2026-03-18",
            "current_price": 178.50,
            "predicted_price": 195.20,
            "confidence": 0.82,
            "analyst_rating": "buy",
            "key_factors": "Strong iPhone sales",
        }]
        script = _template_script("AAPL", "Apple Analysis", None, forecasts)
        assert "178.50" in script
        assert "195.20" in script
        assert "82" in script  # confidence percentage
        assert "Buy" in script


class TestExtractPriceData:
    def test_uses_forecasts_when_available(self):
        from video_generator import _extract_price_data
        from datetime import date
        forecasts = [
            {"forecast_date": date(2026, 3, 17), "current_price": 100.0},
            {"forecast_date": date(2026, 3, 18), "current_price": 105.0},
        ]
        prices, days = _extract_price_data("AAPL", forecasts)
        assert prices == [100.0, 105.0]
        assert len(days) == 2

    def test_simulates_when_no_forecasts(self):
        from video_generator import _extract_price_data
        prices, days = _extract_price_data("TSLA", None)
        assert len(prices) == 7
        assert len(days) == 7
        assert all(isinstance(p, float) for p in prices)


class TestRenderFrames:
    def test_creates_multiple_frames(self, tmp_path):
        from video_generator import _render_frames
        frames = _render_frames("TSLA", None, tmp_path, "test-job-id")
        # Should create at least title + 7 chart frames = 8
        assert len(frames) >= 8
        for f in frames:
            assert Path(f).exists()
            assert f.endswith(".png")

    def test_creates_forecast_frame_when_forecasts_provided(self, tmp_path):
        from video_generator import _render_frames
        forecasts = [{
            "forecast_date": "2026-03-18",
            "current_price": 178.50,
            "predicted_price": 195.20,
            "confidence": 0.82,
            "analyst_rating": "buy",
            "key_factors": "Strong sales",
        }]
        frames = _render_frames("AAPL", forecasts, tmp_path, "test-forecast")
        # title + 1 chart frame + forecast = 3
        assert len(frames) == 3
        assert any("forecast" in f for f in frames)


class TestComposeVideo:
    def test_uses_concatenate_and_24fps(self, tmp_path):
        """_compose_video must concatenate frames and use 24 fps."""
        from video_generator import _compose_video
        from unittest.mock import MagicMock, patch

        mock_audio = MagicMock()
        mock_audio.duration = 10.0

        mock_image = MagicMock()
        mock_image.with_duration.return_value = mock_image

        mock_video = MagicMock()
        mock_video.with_audio.return_value = mock_video

        with (
            patch("video_generator.AudioFileClip", return_value=mock_audio),
            patch("video_generator.ImageClip", return_value=mock_image),
            patch("video_generator.concatenate_videoclips", return_value=mock_video) as mock_concat,
        ):
            result = _compose_video(
                [str(tmp_path / "title.png"), str(tmp_path / "chart.png")],
                str(tmp_path / "audio.mp3"),
                tmp_path,
                "job-xyz",
            )

        mock_concat.assert_called_once()
        mock_video.with_audio.assert_called_once_with(mock_audio)
        mock_video.write_videofile.assert_called_once()
        write_kwargs = mock_video.write_videofile.call_args
        assert write_kwargs.kwargs.get("fps") == 24 or write_kwargs[1].get("fps") == 24
        assert result.endswith("job-xyz.mp4")


class TestGenerateVideo:
    def test_end_to_end_with_mocks(self, tmp_path):
        """Ensure generate_video wires together all sub-steps and returns a path."""
        from video_generator import generate_video

        with (
            patch("video_generator._generate_script", return_value="Test script."),
            patch("video_generator._render_frames", return_value=[str(tmp_path / "f.png")]),
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

    def test_end_to_end_with_forecasts(self, tmp_path):
        """Forecasts parameter is threaded through to sub-steps."""
        from video_generator import generate_video

        forecasts = [{"current_price": 100, "predicted_price": 110}]

        with (
            patch("video_generator._generate_script", return_value="Script.") as mock_script,
            patch("video_generator._render_frames", return_value=[str(tmp_path / "f.png")]) as mock_frames,
            patch("video_generator._synthesise_audio", return_value=str(tmp_path / "a.mp3")),
            patch("video_generator._compose_video", return_value=str(tmp_path / "v.mp4")),
        ):
            generate_video(
                job_id="test-fc",
                stock_symbol="AAPL",
                title=None,
                description=None,
                output_dir=str(tmp_path),
                forecasts=forecasts,
            )

        # Verify forecasts were passed to script and frame generators
        assert mock_script.call_args.args[4] == forecasts or mock_script.call_args.kwargs.get("forecasts") == forecasts
        assert mock_frames.call_args.args[1] == forecasts or mock_frames.call_args.kwargs.get("forecasts") == forecasts
