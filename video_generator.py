"""
Video generator module for the AI video pipeline.

Generates a short stock-analysis video for a given stock symbol by:
  1. Generating a script with the Anthropic Claude API (if an API key is provided)
     or falling back to a template-based script.  Forecast data from the database
     is incorporated when available.
  2. Synthesising an audio narration with gTTS.
  3. Rendering animated chart frames with matplotlib (title card, progressive
     bar build-up, and a forecast overlay).
  4. Combining the frames and audio into a dynamic MP4 with moviepy.
"""

from __future__ import annotations

import logging
import os
import textwrap
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # headless backend – no display required
import matplotlib.pyplot as plt
import numpy as np
from gtts import gTTS
from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

logger = logging.getLogger(__name__)

_CHART_WIDTH = 10
_CHART_HEIGHT = _CHART_WIDTH * 9 / 16  # 16:9 aspect ratio


def generate_video(
    job_id: str,
    stock_symbol: str,
    title: Optional[str],
    description: Optional[str],
    output_dir: str,
    anthropic_api_key: str = "",
    forecasts: Optional[list[dict]] = None,
) -> str:
    """
    Generate a dynamic video for *stock_symbol* and return the path to the MP4.

    Parameters
    ----------
    job_id:             UUID string used to name the output files.
    stock_symbol:       Ticker symbol (e.g. "AAPL").
    title:              Optional video title stored in the database.
    description:        Optional extra context stored in the database.
    output_dir:         Directory where generated files are saved.
    anthropic_api_key:  When provided the script is AI-generated; otherwise a
                        template is used.
    forecasts:          Forecast rows fetched from the asset_forecasts table.

    Returns
    -------
    Absolute path to the generated MP4 file.
    """
    forecasts = forecasts or []
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    script = _generate_script(stock_symbol, title, description, anthropic_api_key, forecasts)
    logger.info("[%s] Script generated (%d chars).", job_id, len(script))

    audio_path = _synthesise_audio(script, output_path, job_id)
    logger.info("[%s] Audio synthesised: %s", job_id, audio_path)

    frame_paths = _render_frames(stock_symbol, forecasts, output_path, job_id)
    logger.info("[%s] Rendered %d frames.", job_id, len(frame_paths))

    video_path = _compose_video(frame_paths, audio_path, output_path, job_id)
    logger.info("[%s] Video composed: %s", job_id, video_path)

    # Clean up intermediate files
    for tmp in list(frame_paths) + [audio_path]:
        try:
            Path(tmp).unlink(missing_ok=True)
        except OSError:
            pass

    return str(video_path)


# ---------------------------------------------------------------------------
# Script generation
# ---------------------------------------------------------------------------

def _generate_script(
    stock_symbol: str,
    title: Optional[str],
    description: Optional[str],
    anthropic_api_key: str,
    forecasts: Optional[list[dict]] = None,
) -> str:
    """Return a narration script for the stock video."""
    if anthropic_api_key:
        try:
            return _claude_script(stock_symbol, title, description, anthropic_api_key, forecasts)
        except Exception as exc:
            logger.warning("Claude script generation failed (%s); using template.", exc)

    return _template_script(stock_symbol, title, description, forecasts)


def _claude_script(
    stock_symbol: str,
    title: Optional[str],
    description: Optional[str],
    anthropic_api_key: str,
    forecasts: Optional[list[dict]] = None,
) -> str:
    """Call the Anthropic Claude API to generate a 30-second narration script."""
    import anthropic  # lazy import – only required when key is present

    client = anthropic.Anthropic(api_key=anthropic_api_key)

    # Build a rich context block from forecast data.
    forecast_context = _format_forecast_context(forecasts)

    context = description or ""
    prompt = (
        f"Write an engaging, data-driven 30-second narration script for a stock "
        f"analysis video about {stock_symbol}."
        + (f" Video title: {title}." if title else "")
        + (f" Additional context: {context}." if context else "")
        + (f"\n\nForecast data:\n{forecast_context}" if forecast_context else "")
        + "\n\nGuidelines:"
        " Reference specific numbers from the forecast data when available."
        " Include the current price, predicted price, analyst rating, and key factors."
        " Keep the tone professional, confident, and informative."
        " Structure: brief hook, price action summary, forecast outlook, closing."
        " Do not include stage directions or timestamps."
    )
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _template_script(
    stock_symbol: str,
    title: Optional[str],
    description: Optional[str],
    forecasts: Optional[list[dict]] = None,
) -> str:
    """Return a template-based narration script when Claude is unavailable."""
    headline = title or f"{stock_symbol} Stock Analysis"
    context = f" {description}" if description else ""

    if forecasts:
        sorted_fc = sorted(forecasts, key=lambda f: str(f.get("forecast_date", "")))
        latest = sorted_fc[-1]
        current = float(latest.get("current_price", 0))
        predicted = float(latest.get("predicted_price", 0))
        confidence = float(latest.get("confidence", 0))
        rating = (latest.get("analyst_rating") or "neutral").capitalize()
        factors = latest.get("key_factors") or "general market conditions"
        change_pct = ((predicted - current) / current * 100) if current else 0
        direction = "upside" if change_pct >= 0 else "downside"

        return textwrap.dedent(f"""
            Welcome to today's AI-powered stock analysis.{context}
            Today we are taking a deep dive into {stock_symbol}. {headline}.
            The current trading price sits at {current:.2f} dollars.
            Our AI model forecasts a move to {predicted:.2f} dollars,
            representing a {abs(change_pct):.1f} percent {direction}.
            This projection carries a confidence level of {confidence * 100:.0f} percent.
            The analyst consensus rating is {rating}.
            Key factors driving this outlook include {factors}.
            Stay informed and make data-driven investment decisions.
            Thank you for watching.
        """).strip()

    return textwrap.dedent(f"""
        Welcome to today's AI-powered stock analysis.{context}
        Today we are looking at {stock_symbol}.
        {headline}.
        Our analysis highlights key price movements and market trends
        for {stock_symbol} over the recent period.
        Stay informed and make data-driven investment decisions.
        Thank you for watching.
    """).strip()


def _format_forecast_context(forecasts: Optional[list[dict]]) -> str:
    """Format forecast rows into a concise text block for the AI prompt."""
    if not forecasts:
        return ""
    sorted_fc = sorted(forecasts, key=lambda f: str(f.get("forecast_date", "")))
    lines = []
    for fc in sorted_fc:
        lines.append(
            f"  {fc.get('forecast_date')}: "
            f"price=${float(fc.get('current_price', 0)):.2f}, "
            f"predicted=${float(fc.get('predicted_price', 0)):.2f}"
        )
    latest = sorted_fc[-1]
    lines.append(f"  Confidence: {float(latest.get('confidence', 0)) * 100:.0f}%")
    lines.append(f"  Rating: {latest.get('analyst_rating', 'N/A')}")
    lines.append(f"  Key factors: {latest.get('key_factors', 'N/A')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Frame rendering
# ---------------------------------------------------------------------------

def _extract_price_data(
    stock_symbol: str,
    forecasts: Optional[list[dict]],
) -> tuple[list[float], list[str]]:
    """Extract price series from forecasts, or simulate when unavailable."""
    if forecasts:
        sorted_fc = sorted(forecasts, key=lambda f: str(f.get("forecast_date", "")))
        prices = [float(fc["current_price"]) for fc in sorted_fc]
        days = [
            fc["forecast_date"].strftime("%b %d")
            if hasattr(fc["forecast_date"], "strftime")
            else str(fc["forecast_date"])
            for fc in sorted_fc
        ]
        return prices, days

    _MAX_RNG_SEED = 2**32
    rng = np.random.default_rng(seed=abs(hash(stock_symbol)) % _MAX_RNG_SEED)
    days = [f"Day {i + 1}" for i in range(7)]
    prices = list(100 + np.cumsum(rng.uniform(-3, 3, size=7)))
    return prices, days


def _render_frames(
    stock_symbol: str,
    forecasts: Optional[list[dict]],
    output_path: Path,
    job_id: str,
) -> list[str]:
    """Render all frames for the animated video and return their file paths."""
    prices, days = _extract_price_data(stock_symbol, forecasts)
    frames: list[str] = []

    # Scene 1 – title card
    frames.append(_render_title_card(stock_symbol, forecasts, output_path, job_id))

    # Scene 2 – progressive chart build-up (one bar added per frame)
    for step in range(1, len(prices) + 1):
        frames.append(
            _render_chart_frame(stock_symbol, prices, days, step, output_path, job_id)
        )

    # Scene 3 – forecast overlay (only when we have forecast data)
    if forecasts:
        frames.append(
            _render_forecast_frame(stock_symbol, prices, days, forecasts, output_path, job_id)
        )

    return frames


def _render_title_card(
    stock_symbol: str,
    forecasts: Optional[list[dict]],
    output_path: Path,
    job_id: str,
) -> str:
    """Render a title card frame and return the file path."""
    fig, ax = plt.subplots(figsize=(_CHART_WIDTH, _CHART_HEIGHT))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#1a1a2e")

    ax.text(0.5, 0.65, stock_symbol, fontsize=48, color="white",
            ha="center", va="center", fontweight="bold")
    ax.text(0.5, 0.45, "AI Stock Analysis", fontsize=24, color="#2ecc71",
            ha="center", va="center")

    if forecasts:
        sorted_fc = sorted(forecasts, key=lambda f: str(f.get("forecast_date", "")))
        rating = (sorted_fc[-1].get("analyst_rating") or "").upper()
        if rating:
            ax.text(0.5, 0.30, f"Analyst Rating: {rating}", fontsize=18,
                    color="#e0e0e0", ha="center", va="center")

    title_path = str(output_path / f"{job_id}_title.png")
    fig.savefig(title_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return title_path


def _render_chart_frame(
    stock_symbol: str,
    prices: list[float],
    days: list[str],
    visible_bars: int,
    output_path: Path,
    job_id: str,
) -> str:
    """Render one chart frame with *visible_bars* bars visible."""
    fig, ax = plt.subplots(figsize=(_CHART_WIDTH, _CHART_HEIGHT))

    x_positions = list(range(len(days)))
    vis_prices = prices[:visible_bars]
    vis_x = x_positions[:visible_bars]
    colors = [
        "#2ecc71" if p >= prices[max(0, i - 1)] else "#e74c3c"
        for i, p in enumerate(vis_prices)
    ]

    ax.bar(vis_x, vis_prices, color=colors, edgecolor="white", linewidth=0.5)

    ax.set_xticks(x_positions)
    ax.set_xticklabels(days, fontsize=10)
    ax.set_xlim(-0.5, len(days) - 0.5)
    ax.set_title(f"{stock_symbol} – Price Movement", fontsize=18, pad=15)
    ax.set_ylabel("Price (USD)", fontsize=12)
    ax.set_ylim(min(prices) * 0.97, max(prices) * 1.03)

    _apply_dark_theme(fig, ax)
    plt.tight_layout()

    frame_path = str(output_path / f"{job_id}_chart_{visible_bars}.png")
    fig.savefig(frame_path, dpi=150)
    plt.close(fig)
    return frame_path


def _render_forecast_frame(
    stock_symbol: str,
    prices: list[float],
    days: list[str],
    forecasts: list[dict],
    output_path: Path,
    job_id: str,
) -> str:
    """Render a chart frame with forecast data overlaid."""
    fig, ax = plt.subplots(figsize=(_CHART_WIDTH, _CHART_HEIGHT))

    x_positions = list(range(len(days)))
    colors = [
        "#2ecc71" if p >= prices[max(0, i - 1)] else "#e74c3c"
        for i, p in enumerate(prices)
    ]
    ax.bar(x_positions, prices, color=colors, edgecolor="white", linewidth=0.5)

    ax.set_xticks(x_positions)
    ax.set_xticklabels(days, fontsize=10)
    ax.set_xlim(-0.5, len(days) - 0.5)

    sorted_fc = sorted(forecasts, key=lambda f: str(f.get("forecast_date", "")))
    latest = sorted_fc[-1]
    predicted = float(latest.get("predicted_price", prices[-1]))
    confidence = float(latest.get("confidence", 0.5))

    ax.axhline(y=predicted, color="#f39c12", linestyle="--", linewidth=2,
               label=f"Predicted: ${predicted:.2f}")
    ax.annotate(
        f"Forecast: ${predicted:.2f}\nConfidence: {confidence * 100:.0f}%",
        xy=(len(days) - 1, prices[-1]),
        xytext=(len(days) - 1, predicted),
        fontsize=12, color="#f39c12", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#f39c12", lw=2),
    )
    ax.legend(fontsize=12, facecolor="#16213e", edgecolor="#444", labelcolor="white")

    y_min = min(min(prices), predicted) * 0.95
    y_max = max(max(prices), predicted) * 1.05
    ax.set_ylim(y_min, y_max)
    ax.set_title(f"{stock_symbol} – Forecast Overview", fontsize=18, pad=15)
    ax.set_ylabel("Price (USD)", fontsize=12)

    _apply_dark_theme(fig, ax)
    plt.tight_layout()

    forecast_path = str(output_path / f"{job_id}_forecast.png")
    fig.savefig(forecast_path, dpi=150)
    plt.close(fig)
    return forecast_path


def _apply_dark_theme(fig: plt.Figure, ax: plt.Axes) -> None:
    """Apply the dark colour theme to a chart figure."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")
    ax.tick_params(colors="white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")


# ---------------------------------------------------------------------------
# Audio synthesis
# ---------------------------------------------------------------------------

def _synthesise_audio(script: str, output_path: Path, job_id: str) -> str:
    """Convert *script* to speech using gTTS and return the MP3 file path."""
    audio_file = str(output_path / f"{job_id}_audio.mp3")
    tts = gTTS(text=script, lang="en", slow=False)
    tts.save(audio_file)
    return audio_file


# ---------------------------------------------------------------------------
# Video composition
# ---------------------------------------------------------------------------

def _compose_video(
    frame_paths: list[str],
    audio_path: str,
    output_path: Path,
    job_id: str,
) -> str:
    """Combine multiple animated frames and audio narration into an MP4 file."""
    audio_clip = AudioFileClip(audio_path)
    total_duration = audio_clip.duration
    num_frames = len(frame_paths)

    # Distribute time across frames: title gets a fixed share, forecast gets
    # a fixed share, and chart-building frames share the remainder equally.
    has_forecast = num_frames > 2  # title + at least 1 chart + forecast
    title_duration = min(3.0, total_duration * 0.15)
    forecast_duration = min(4.0, total_duration * 0.20) if has_forecast else 0.0
    remaining = total_duration - title_duration - forecast_duration
    chart_count = num_frames - (2 if has_forecast else 1)
    chart_duration = remaining / max(chart_count, 1)

    clips = []
    for i, frame_path in enumerate(frame_paths):
        if i == 0:
            dur = title_duration
        elif has_forecast and i == num_frames - 1:
            dur = forecast_duration
        else:
            dur = chart_duration
        clips.append(ImageClip(frame_path).with_duration(dur))

    video = concatenate_videoclips(clips, method="compose")
    video = video.with_audio(audio_clip)

    video_file = str(output_path / f"{job_id}.mp4")
    video.write_videofile(
        video_file,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None,  # suppress moviepy progress bars
    )
    audio_clip.close()
    video.close()
    for clip in clips:
        clip.close()
    return video_file
