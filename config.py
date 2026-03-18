"""
Configuration module for the AI video pipeline.

Reads settings from environment variables (or a .env file).
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            "Copy .env.example to .env and fill in the values."
        )
    return value


# Database
PG_CONNECTION_STRING: str = _require_env("PG_CONNECTION_STRING")

# Optional: CockroachDB Cloud cluster CA certificate download URL.
# When set, the certificate is automatically downloaded to
# ~/.postgresql/root.crt so that sslmode=verify-full works out of the box.
CRDB_CA_CERT_URL: str = os.environ.get("CRDB_CA_CERT_URL", "")

# OpenAI
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

# Output directory for generated videos
OUTPUT_DIR: str = os.environ.get("OUTPUT_DIR", "./output")

# Pipeline settings
PIPELINE_BATCH_SIZE: int = int(os.environ.get("PIPELINE_BATCH_SIZE", "10"))
PIPELINE_POLL_INTERVAL_SECONDS: int = int(
    os.environ.get("PIPELINE_POLL_INTERVAL_SECONDS", "60")
)
