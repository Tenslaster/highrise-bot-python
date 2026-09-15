import logging
import sys
from enum import IntEnum
from datetime import datetime, timezone

class LoggerLevel(IntEnum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

class SDKFormatter(logging.Formatter):
    """Custom logger formatter with white name, optional timestamps, and level colors."""
    WHITE = "\x1b[37;1m"
    GREY = "\x1b[38;20m"
    BLUE = "\x1b[34;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    LEVEL_COLORS = {
        LoggerLevel.DEBUG: GREY,
        LoggerLevel.INFO: BLUE,
        LoggerLevel.WARNING: YELLOW,
        LoggerLevel.ERROR: RED,
        LoggerLevel.CRITICAL: BOLD_RED,
    }

    def __init__(self, show_time: bool = False, use_color: bool = True):
        super().__init__()
        self.show_time = show_time
        self.use_color = use_color
        self.time_part = "[%(asctime)s] - " if show_time else ""
        self._formatters: dict[int, logging.Formatter] = {}

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """Formats timestamp into YYYY/MM/DD | HH:MM:SS (24h) UTC format."""
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime("%Y/%m/%d | %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        formatter = self._formatters.get(record.levelno)
        if formatter is None:
            if self.use_color:
                level_color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
                name_open, name_close = self.WHITE, self.RESET
                level_open, level_close = level_color, self.RESET
            else:
                name_open = name_close = level_open = level_close = ""

            fmt = (
                f"{self.time_part}"
                f"[{name_open}%(name)s{name_close}] - "
                f"[{level_open}%(levelname)s{level_close}] - %(message)s"
            )
            formatter = logging.Formatter(fmt)
            if self.show_time:
                formatter.formatTime = self.formatTime
            self._formatters[record.levelno] = formatter

        return formatter.format(record)

def setup_logger(
    name: str = "HighriseBot",
    level: LoggerLevel = LoggerLevel.DEBUG,
    show_time: bool = True,
) -> logging.Logger:
    """Configures and returns an SDK logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if logger.handlers:
        logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(SDKFormatter(show_time=show_time, use_color=sys.stdout.isatty()))
    logger.addHandler(handler)
    logger.propagate = False
    return logger