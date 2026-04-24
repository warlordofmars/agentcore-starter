# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for logging_config.py — no AWS deps."""

from __future__ import annotations

import importlib.metadata
import json
import logging
import os


class TestJsonFormatterExcInfo:
    def test_exc_info_adds_error_type_and_stack_trace(self):
        """Covers logging_config.py:70-71 — exc_info branch in _JsonFormatter.format()."""
        from hive.logging_config import _JsonFormatter

        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="hive.test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Something went wrong",
            args=(),
            exc_info=None,
        )

        # Inject exc_info manually to simulate a logger.exception() call
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            record.exc_info = sys.exc_info()

        output = formatter.format(record)
        data = json.loads(output)
        assert data["error_type"] == "ValueError"
        assert "stack_trace" in data
        assert "test error" in data["stack_trace"]


class TestConfigureLoggingPackageNotFound:
    def test_version_falls_back_to_app_version_env(self):
        """Covers logging_config.py:87-88 — PackageNotFoundError fallback."""
        from unittest.mock import patch

        import hive.logging_config as lc

        env = {k: v for k, v in os.environ.items()}
        env["APP_VERSION"] = "test-fallback-version"

        with (
            patch.dict(os.environ, env),
            patch(
                "hive.logging_config.importlib.metadata.version",
                side_effect=importlib.metadata.PackageNotFoundError,
            ),
        ):
            lc.configure_logging("test-svc")

        assert lc._VERSION == "test-fallback-version"
