"""
Pipeline orchestration for the AI video pipeline.

The main entry point is `run_once()`, which processes one batch of pending
jobs from the `pipeline_videos_stocks_ia` table.  `run_continuous()` loops
indefinitely, sleeping between batches.
"""

from __future__ import annotations

import logging
import time

import config
import database
from video_generator import generate_video

logger = logging.getLogger(__name__)


def run_once(batch_size: int | None = None) -> int:
    """
    Fetch pending jobs and generate a video for each one.

    Parameters
    ----------
    batch_size: Maximum number of jobs to process. Defaults to
                ``config.PIPELINE_BATCH_SIZE``.

    Returns
    -------
    Number of jobs successfully completed in this run.
    """
    if batch_size is None:
        batch_size = config.PIPELINE_BATCH_SIZE

    jobs = database.fetch_pending_jobs(limit=batch_size)
    if not jobs:
        logger.info("No pending jobs found.")
        return 0

    logger.info("Processing %d pending job(s).", len(jobs))
    completed = 0

    for job in jobs:
        job_id = str(job["id"])
        stock_symbol = job["stock_symbol"]
        logger.info("[%s] Starting video generation for %s.", job_id, stock_symbol)

        database.mark_processing(job_id)
        try:
            output_path = generate_video(
                job_id=job_id,
                stock_symbol=stock_symbol,
                title=job.get("title"),
                description=job.get("description"),
                output_dir=config.OUTPUT_DIR,
                openai_api_key=config.OPENAI_API_KEY,
            )
            database.mark_completed(job_id, output_path)
            logger.info("[%s] Completed. Video saved to: %s", job_id, output_path)
            completed += 1
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.exception("[%s] Video generation failed: %s", job_id, error_msg)
            database.mark_failed(job_id, error_msg)

    return completed


def run_continuous(
    poll_interval: int | None = None,
    batch_size: int | None = None,
) -> None:
    """
    Run the pipeline in a continuous loop, polling for new jobs.

    Parameters
    ----------
    poll_interval:  Seconds to sleep between batches. Defaults to
                    ``config.PIPELINE_POLL_INTERVAL_SECONDS``.
    batch_size:     Passed to ``run_once()``.
    """
    if poll_interval is None:
        poll_interval = config.PIPELINE_POLL_INTERVAL_SECONDS

    logger.info(
        "Starting continuous pipeline (poll_interval=%ds, batch_size=%s).",
        poll_interval,
        batch_size or config.PIPELINE_BATCH_SIZE,
    )
    while True:
        try:
            run_once(batch_size=batch_size)
        except Exception as exc:
            logger.exception("Unexpected pipeline error: %s", exc)
        logger.info("Sleeping %d seconds before next poll.", poll_interval)
        time.sleep(poll_interval)
