import os
from shelfmark.config.env import INGEST_DIR, TMP_DIR

SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8080"))
SERVER_API_KEY = os.environ.get("SERVER_API_KEY", "")
SERVER_DEBUG = os.environ.get("SERVER_DEBUG", "").lower() == "true"

__all__ = [
    "SERVER_HOST",
    "SERVER_PORT",
    "SERVER_API_KEY",
    "SERVER_DEBUG",
    "INGEST_DIR",
    "TMP_DIR",
]
