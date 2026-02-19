import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger with consistent formatting for the job_processor service.
    Logs are written to stdout (for systemd/journalctl capture) and to a rotating file.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if get_logger is called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # --- Formatter ---
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # --- Console Handler (for systemd / stdout) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # --- Rotating File Handler ---
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            "job_processor.log",
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass  # If log file is not writable (e.g. read-only FS), skip silently

    logger.addHandler(console_handler)
    return logger
