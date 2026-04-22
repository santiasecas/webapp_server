"""
Centralized logging configuration.
"""
import logging
import logging.handlers
import sys
from pathlib import Path

from core.config import settings


def setup_logging() -> None:
    """Configure logging for the entire platform."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handlers = []

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(logging.Formatter(settings.LOG_FORMAT))
    handlers.append(console)

    # File handler (optional)
    if settings.LOG_FILE:
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(settings.LOG_FORMAT))
        handlers.append(file_handler)

    # Root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True,
    )

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DB_ECHO else logging.WARNING
    )

    logging.getLogger(__name__).info(
        f"Logging configured: level={settings.LOG_LEVEL}, file={settings.LOG_FILE or 'none'}"
    )
