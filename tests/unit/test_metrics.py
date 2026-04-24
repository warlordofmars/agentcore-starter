# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for hive.metrics EMF wrapper."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestEmitMetric:
    @pytest.mark.asyncio
    async def test_emits_count_metric(self):
        """emit_metric flushes a MetricsLogger with the right namespace and metric."""
        mock_logger = MagicMock()
        mock_logger.flush = AsyncMock()

        with patch("hive.metrics.create_metrics_logger", return_value=mock_logger):
            from hive.metrics import emit_metric

            await emit_metric("ToolInvocations", operation="remember")

        mock_logger.set_namespace.assert_called_once_with("Hive")
        mock_logger.put_metric.assert_called_once_with("ToolInvocations", 1.0, "Count")
        mock_logger.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_emits_custom_value_and_unit(self):
        mock_logger = MagicMock()
        mock_logger.flush = AsyncMock()

        with patch("hive.metrics.create_metrics_logger", return_value=mock_logger):
            from hive.metrics import emit_metric

            await emit_metric(
                "StorageLatencyMs", value=42.0, unit="Milliseconds", operation="recall"
            )

        mock_logger.put_metric.assert_called_once_with("StorageLatencyMs", 42.0, "Milliseconds")

    @pytest.mark.asyncio
    async def test_dimensions_include_environment(self):
        mock_logger = MagicMock()
        mock_logger.flush = AsyncMock()

        with patch("hive.metrics.create_metrics_logger", return_value=mock_logger):
            import hive.metrics as m

            original = m.ENVIRONMENT
            m.ENVIRONMENT = "prod"
            try:
                await m.emit_metric("ToolErrors", operation="forget")
            finally:
                m.ENVIRONMENT = original

        call_args = mock_logger.set_dimensions.call_args[0][0]
        assert call_args["Environment"] == "prod"
        assert call_args["operation"] == "forget"

    @pytest.mark.asyncio
    async def test_defaults_environment_to_local(self):
        """ENVIRONMENT defaults to 'local' when HIVE_ENV and ENV are unset."""
        env = {k: v for k, v in os.environ.items() if k not in ("HIVE_ENV", "ENV")}
        with patch.dict(os.environ, env, clear=True):
            import importlib

            import hive.metrics as m

            importlib.reload(m)
            assert m.ENVIRONMENT == "local"
