"""
Video generator module for the AI video pipeline.

Generates a short stock-analysis video for a given stock symbol by:
  1. Generating a script with the OpenAI Chat API (if an API key is provided)
     or falling back to a template-based script.
  2. Synthesising an audio narration with gTTS.
  3. Creating a bar chart image with matplotlib.
  4. Combining chart and audio into an MP4 with moviepy.
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
from moviepy import AudioFileClip, ImageClip

logger = logging.getLogger(__name__)


def generate_video(
    job_id: str,
    stock_symbol: str,
    title: Optional[str],
    description: Optional[str],
    output_dir: str,
    openai_api_key: str = "",
) -> str:
    """
    Generate a video for *stock_symbol* and return the path to the MP4 file.

    Parameters
    ----------
    job_id:          UUID string used to name the output files.
    stock_symbol:    Ticker symbol (e.g. "AAPL").
    title:           Optional video title stored in the database.
    description:     Optional extra context stored in the database.
    output_dir:      Directory where generated files are saved.
    openai_api_key:  When provided the script is AI-generated; otherwise a
                     template is used.

    Returns
    -------
    Absolute path to the generated MP4 file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    script = _generate_script(stock_symbol, title, description, openai_api_key)
    logger.info("[%s] Script generated (%d chars).", job_id, len(script))

    chart_path = _render_chart(stock_symbol, output_path, job_id)
    logger.info("[%s] Chart rendered: %s", job_id, chart_path)

    audio_path = _synthesise_audio(script, output_path, job_id)
    logger.info("[%s] Audio synthesised: %s", job_id, audio_path)

    video_path = _compose_video(chart_path, audio_path, output_path, job_id)
    logger.info("[%s] Video composed: %s", job_id, video_path)

    # Clean up intermediate files
    for tmp in (chart_path, audio_path):
        try:
            Path(tmp).unlink(missing_ok=True)
        except OSError:
            pass

    return str(video_path)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _generate_script(
    stock_symbol: str,
    title: Optional[str],
    description: Optional[str],
    openai_api_key: str,
) -> str:
    """Return a narration script for the stock video."""
    if openai_api_key:
        try:
            return _openai_script(stock_symbol, title, description, openai_api_key)
        except Exception as exc:
            logger.warning("OpenAI script generation failed (%s); using template.", exc)

    return _template_script(stock_symbol, title, description)


def _openai_script(
    stock_symbol: str,
    title: Optional[str],
    description: Optional[str],
    openai_api_key: str,
) -> str:
    """Call the OpenAI Chat API to generate a 30-second narration script."""
    import openai  # lazy import – only required when key is present

    client = openai.OpenAI(api_key=openai_api_key)
    context = description or ""
    prompt = (
        f"Write a concise, engaging 30-second narration script for a stock analysis "
        f"video about {stock_symbol}."
        + (f" Video title: {title}." if title else "")
        + (f" Additional context: {context}." if context else "")
        + " Keep the tone professional and informative. Do not include stage directions."
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


def _template_script(
    stock_symbol: str,
    title: Optional[str],
    description: Optional[str],
) -> str:
    """Return a template-based narration script when OpenAI is unavailable."""
    headline = title or f"{stock_symbol} Stock Analysis"
    context = f" {description}" if description else ""
    return textwrap.dedent(f"""
        Welcome to today's AI-powered stock analysis.{context}
        Today we are looking at {stock_symbol}.
        {headline}.
        Our analysis highlights key price movements and market trends
        for {stock_symbol} over the recent period.
        Stay informed and make data-driven investment decisions.
        Thank you for watching.
    """).strip()


def _render_chart(stock_symbol: str, output_path: Path, job_id: str) -> str:
    """Render a simulated price-movement bar chart and return the file path."""
    _MAX_RNG_SEED = 2**31  # numpy default_rng requires seed within [0, 2^32)
    rng = np.random.default_rng(seed=abs(hash(stock_symbol)) % _MAX_RNG_SEED)
    days = [f"Day {i+1}" for i in range(7)]
    prices = 100 + np.cumsum(rng.uniform(-3, 3, size=7))

    _CHART_WIDTH = 10
    _CHART_HEIGHT = _CHART_WIDTH * 9 / 16  # 16:9 aspect ratio
    fig, ax = plt.subplots(figsize=(_CHART_WIDTH, _CHART_HEIGHT))
    colors = ["#2ecc71" if p >= prices[max(0, i - 1)] else "#e74c3c"
              for i, p in enumerate(prices)]
    ax.bar(days, prices, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_title(f"{stock_symbol} – 7-Day Price Movement", fontsize=18, pad=15)
    ax.set_ylabel("Price (USD)", fontsize=12)
    ax.set_ylim(min(prices) * 0.97, max(prices) * 1.03)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")
    ax.tick_params(colors="white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    plt.tight_layout()

    chart_file = str(output_path / f"{job_id}_chart.png")
    fig.savefig(chart_file, dpi=150)
    plt.close(fig)
    return chart_file


def _synthesise_audio(script: str, output_path: Path, job_id: str) -> str:
    """Convert *script* to speech using gTTS and return the MP3 file path."""
    audio_file = str(output_path / f"{job_id}_audio.mp3")
    tts = gTTS(text=script, lang="en", slow=False)
    tts.save(audio_file)
    return audio_file


def _compose_video(
    chart_path: str,
    audio_path: str,
    output_path: Path,
    job_id: str,
) -> str:
    """Combine chart image and audio narration into an MP4 file."""
    audio_clip = AudioFileClip(audio_path)
    image_clip = (
        ImageClip(chart_path)
        .set_duration(audio_clip.duration)
        .set_audio(audio_clip)
    )
    video_file = str(output_path / f"{job_id}.mp4")
    image_clip.write_videofile(
        video_file,
        fps=1,
        codec="libx264",
        audio_codec="aac",
        logger=None,  # suppress moviepy progress bars
    )
    audio_clip.close()
    image_clip.close()
    return video_file
