import logging

from .config import settings

_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        logging.basicConfig(
            level=getattr(logging, str(settings.logger_config.LOG_LEVEL).upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        _configured = True
    return logging.getLogger(name)


__all__ = ["get_logger", "settings"]
