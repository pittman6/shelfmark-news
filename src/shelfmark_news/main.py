"""Main application entry point for shelfmark-news.

This creates a FastAPI application that provides Newznab and SABnzbd
compatible APIs for book searching and downloading.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ponytaill: shelfmark submodule has [tool.uv] package=false, so inject its
# source directory onto sys.path so the shelfmark package is importable.
_shelfmark_src = Path(__file__).parent.parent.parent / "shelfmark"
if str(_shelfmark_src) not in sys.path:
    sys.path.insert(0, str(_shelfmark_src))

# Allow imports after the src editing
from shelfmark_news import __version__  # noqa: E402
from shelfmark_news.newznab import router as newznab_router  # noqa: E402
from shelfmark_news.sabnzbd import router as sabnzbd_router  # noqa: E402
from shelfmark_news.config import (  # noqa: E402
    SERVER_DEBUG,
    SERVER_HOST,
    SERVER_PORT,
    SERVER_API_KEY,
    INGEST_DIR,
    TMP_DIR,
)

RESET = "\033[0m"
COLORS = {
    logging.DEBUG: "\033[36m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;31m",
}


class _ColoredFormatter(logging.Formatter):
    def format(self, record):
        color = COLORS.get(record.levelno, "")
        record.levelname = f"{color}{record.levelname}{RESET}"
        record.name = f"{color}{record.name}{RESET}"
        return super().format(record)


handler = logging.StreamHandler()
handler.setFormatter(
    _ColoredFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")
)
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)


os.environ.setdefault(
    "CONFIG_DIR", str(Path(__file__).parent.parent.parent / "data" / "config")
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    INGEST_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Output directory: %s", INGEST_DIR)
    logger.info("Temp directory: %s", TMP_DIR)

    try:
        from shelfmark.download.orchestrator import start as start_orchestrator

        start_orchestrator()
        logger.info("Download orchestrator started")
    except ImportError as e:
        logger.warning("Could not start orchestrator: %s", e)

    yield

    logger.info("Shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Shelfmark News",
        description="Newznab/SABnzbd API wrapper for book searching and downloading",
        version=__version__,
        lifespan=lifespan,
        debug=SERVER_DEBUG,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(newznab_router)
    app.include_router(sabnzbd_router)

    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "Shelfmark News",
            "version": __version__,
            "description": "Newznab/SABnzbd API wrapper for book searching",
            "endpoints": {
                "newznab": "/api?t=caps",
                "sabnzbd": "/sabnzbd/api?mode=version",
            },
        }

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy", "version": __version__}

    return app


app = create_app()


def main():
    """Main entry point for running the server."""
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Shelfmark News server")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging and auto-reload",
    )
    args = parser.parse_args()

    if args.debug:
        os.environ["SERVER_DEBUG"] = "true"

    debug = os.environ.get("SERVER_DEBUG", "").lower() == "true"

    logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

    logger.info("Starting Shelfmark News v%s", __version__)
    logger.info("Server: %s:%d", SERVER_HOST, SERVER_PORT)

    if not SERVER_API_KEY:
        logger.warning("No API key configured - API is open!")

    uvicorn.run(
        "shelfmark_news.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=debug,
        log_level="debug" if debug else "info",
    )


if __name__ == "__main__":
    main()
