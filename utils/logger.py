"""Logging configuration for Paper Notes."""

import logging
import sys
from pathlib import Path


def setup_logging(
    level: int = logging.INFO,
    log_file: str | Path | None = None,
) -> logging.Logger:
    """Configure and return the root application logger.

    Logs to stderr by default. Optionally also logs to a file.

    Args:
        level: Logging level (default INFO).
        log_file: Optional path to a log file for persistent logging.

    Returns:
        The root logger for the application.
    """
    logger = logging.getLogger("paper_notes")
    logger.setLevel(level)

    # Avoid adding duplicate handlers on repeated calls.
    if logger.handlers:
        return logger

    # Console handler (stderr).
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console.setFormatter(fmt)
    logger.addHandler(console)

    # Optional file handler.
    if log_file is not None:
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module.

    Args:
        name: Module name (e.g. 'pdf.importer').

    Returns:
        A logger instance.
    """
    return logging.getLogger(f"paper_notes.{name}")
