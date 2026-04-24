# Copyright (c) 2026 John Carter. All rights reserved.
"""Unit tests for the hybrid search scoring helpers (#481)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hive.hybrid_search import (
    DEFAULT_W_KEYWORD,
    DEFAULT_W_RECENCY,
    DEFAULT_W_SEMANTIC,
    blend_score,
    keyword_score,
    recency_score,
    tokenize,
)
from hive.models import Memory


class TestTokenize:
    def test_lowercases_and_splits_on_non_word(self):
        assert tokenize("Hello, World! 2026") == ["hello", "world", "2026"]

    def test_empty_string_returns_empty_list(self):
        assert tokenize("") == []

    def test_unicode_word_chars(self):
        # \w is Unicode-aware under the re.UNICODE flag.
        assert tokenize("café Résumé") == ["café", "résumé"]


class TestKeywordScore:
    def test_returns_fraction_of_tokens_matched(self):
        assert keyword_score(["wifi", "password"], "the wifi password is 1234") == 1.0
        assert keyword_score(["wifi", "password"], "the wifi is up") == 0.5
        assert keyword_score(["wifi", "password"], "nothing to see") == 0.0

    def test_empty_query_returns_zero(self):
        assert keyword_score([], "any value") == 0.0

    def test_empty_value_returns_zero(self):
        assert keyword_score(["wifi"], "") == 0.0

    def test_value_tokenisation_is_case_insensitive(self):
        # The scorer assumes query tokens are already lowercased via tokenize();
        # this test verifies it still matches when the value has mixed case.
        assert keyword_score(tokenize("WIFI"), "WIFI works") == 1.0
        assert keyword_score(tokenize("WiFi"), "the WIFI password") == 1.0


class TestRecencyScore:
    def _mem(self, *, updated_at=None, last_accessed_at=None) -> Memory:
        return Memory(
            key="k",
            value="v",
            owner_client_id="c1",
            updated_at=updated_at or datetime.now(timezone.utc),
            last_accessed_at=last_accessed_at,
        )

    def test_fresh_memory_scores_near_one(self):
        now = datetime.now(timezone.utc)
        m = self._mem(updated_at=now)
        assert recency_score(m, now=now) == 1.0

    def test_half_life_produces_half_score(self):
        now = datetime(2026, 1, 31, tzinfo=timezone.utc)
        m = self._mem(updated_at=now - timedelta(days=30))
        assert abs(recency_score(m, now=now, half_life_days=30) - 0.5) < 1e-6

    def test_uses_last_accessed_at_when_set(self):
        now = datetime(2026, 1, 31, tzinfo=timezone.utc)
        # updated_at is old but last_accessed_at is fresh — recency should be high.
        m = self._mem(
            updated_at=now - timedelta(days=365),
            last_accessed_at=now,
        )
        assert recency_score(m, now=now) == 1.0

    def test_future_timestamps_clamped_to_now(self):
        now = datetime(2026, 1, 31, tzinfo=timezone.utc)
        m = self._mem(updated_at=now + timedelta(days=10))
        # Future ref shouldn't blow up; age is clamped to 0 → score 1.0.
        assert recency_score(m, now=now) == 1.0


class TestBlendScore:
    def test_weighted_sum(self):
        # With defaults: 0.6 * 1 + 0.3 * 0 + 0.1 * 0 = 0.6
        assert blend_score(semantic=1.0, keyword=0.0, recency=0.0) == pytest.approx(0.6)

    def test_renormalises_uneven_weights(self):
        # Weights 2:2:0 should behave like 0.5 / 0.5 / 0
        score = blend_score(
            semantic=1.0,
            keyword=0.0,
            recency=0.0,
            w_semantic=2.0,
            w_keyword=2.0,
            w_recency=0.0,
        )
        assert score == pytest.approx(0.5)

    def test_all_zero_weights_falls_back_to_defaults(self):
        # Shouldn't produce NaN or zero when caller passes all-zero weights.
        score = blend_score(
            semantic=1.0,
            keyword=0.5,
            recency=0.25,
            w_semantic=0,
            w_keyword=0,
            w_recency=0,
        )
        expected = DEFAULT_W_SEMANTIC * 1.0 + DEFAULT_W_KEYWORD * 0.5 + DEFAULT_W_RECENCY * 0.25
        assert score == pytest.approx(expected)

    def test_all_ones_produces_one(self):
        assert blend_score(semantic=1.0, keyword=1.0, recency=1.0) == pytest.approx(1.0)
