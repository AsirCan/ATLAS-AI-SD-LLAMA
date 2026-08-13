"""Rotating application log configuration."""

import logging

from core.runtime.logging_config import SecretRedactionFilter, configure_logging


def test_secret_filter_masks_common_credentials():
    record = logging.LogRecord(
        "test",
        logging.ERROR,
        __file__,
        1,
        "password=super-secret access_token:abc123",
        (),
        None,
    )

    assert SecretRedactionFilter().filter(record) is True
    assert "super-secret" not in record.getMessage()
    assert "abc123" not in record.getMessage()
    assert record.getMessage().count("[REDACTED]") == 2


def test_rotating_file_handler_writes_and_rotates(tmp_path):
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    old_configured = getattr(root, "_atlas_configured", None)
    old_path = getattr(root, "_atlas_log_path", None)

    for handler in old_handlers:
        root.removeHandler(handler)
    for attr in ("_atlas_configured", "_atlas_log_path"):
        if hasattr(root, attr):
            delattr(root, attr)

    try:
        log_path = configure_logging(log_dir=tmp_path, max_bytes=180, backup_count=2)
        test_logger = logging.getLogger("atlas.rotation.test")
        for index in range(30):
            test_logger.error("rotation-line-%s %s", index, "x" * 40)
        for handler in root.handlers:
            handler.flush()

        assert log_path == tmp_path / "atlas.log"
        assert log_path.exists()
        assert (tmp_path / "atlas.log.1").exists()
    finally:
        for handler in list(root.handlers):
            handler.close()
            root.removeHandler(handler)
        root.handlers.extend(old_handlers)
        root.setLevel(old_level)
        if old_configured is not None:
            setattr(root, "_atlas_configured", old_configured)
        if old_path is not None:
            setattr(root, "_atlas_log_path", old_path)
