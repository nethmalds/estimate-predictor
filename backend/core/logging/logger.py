import logging
import sys


_DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str | None = None) -> None:
    log_level = (level or "INFO").upper()
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(log_level)
        return

    logging.basicConfig(
        level=log_level,
        format=_DEFAULT_FORMAT,
        datefmt=_DATE_FORMAT,
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
