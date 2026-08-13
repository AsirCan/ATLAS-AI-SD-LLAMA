"""Central logging configuration for console and rotating file output."""

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_SENSITIVE_VALUE = re.compile(r"(?i)(access[_-]?token|api[_-]?key|password|secret|authorization)(\s*[:=]\s*)([^\s,;]+)")


class SecretRedactionFilter(logging.Filter):
    """Redact common credential fields before records reach any handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = _SENSITIVE_VALUE.sub(r"\1\2[REDACTED]", message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging(
    *,
    log_dir: str | Path | None = None,
    level: int | str | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> Path | None:
    """Configure root logging once and return the active log file path."""
    root = logging.getLogger()
    if getattr(root, "_atlas_configured", False):
        return getattr(root, "_atlas_log_path", None)

    configured_level = level or os.getenv("ATLAS_LOG_LEVEL", "INFO")
    root.setLevel(configured_level)

    formatter = logging.Formatter(_DEFAULT_FORMAT, datefmt=_DEFAULT_DATE_FORMAT)
    redaction_filter = SecretRedactionFilter()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.addFilter(redaction_filter)
    root.addHandler(console)

    target_dir = Path(log_dir or os.getenv("ATLAS_LOG_DIR", Path(__file__).resolve().parents[2] / "logs"))
    log_path: Path | None = target_dir / "atlas.log"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        rotating = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes or int(os.getenv("ATLAS_LOG_MAX_BYTES", str(5 * 1024 * 1024))),
            backupCount=backup_count or int(os.getenv("ATLAS_LOG_BACKUP_COUNT", "5")),
            encoding="utf-8",
        )
        rotating.setFormatter(formatter)
        rotating.addFilter(redaction_filter)
        root.addHandler(rotating)
    except OSError:
        log_path = None
        root.exception("Rotating log file could not be initialized; console logging remains active")

    setattr(root, "_atlas_configured", True)
    setattr(root, "_atlas_log_path", log_path)
    return log_path
