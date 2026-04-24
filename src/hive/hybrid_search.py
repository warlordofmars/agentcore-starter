# Copyright (c) 2026 John Carter. All rights reserved.
"""
Hybrid retrieval scoring for `search_memories` (#481).

Combines three independent signals into a single blended score:

- **semantic** — cosine similarity from the S3 Vectors index (already
  in the 0-1 range from the vector store).
- **keyword** — cheap term-frequency match over the query tokens
  against the memory value. Gives short/exact-match queries (e.g.
  "wifi password") a meaningful score even when they fall outside
  the embedding neighbourhood.
- **recency** — exponential decay against ``last_accessed_at``
  (falling back to ``updated_at`` when the memory has never been
  recalled). Half-life defaults to 30 days.

Deliberately uses a simple TF heuristic rather than BM25 to avoid
adding a tokeniser dependency — memory values are short, so the
heuristic is good enough. Tokenisation is case-insensitive, no
stemming.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from hive.models import Memory

DEFAULT_W_SEMANTIC = 0.6
DEFAULT_W_KEYWORD = 0.3
DEFAULT_W_RECENCY = 0.1
DEFAULT_RECENCY_HALF_LIFE_DAYS = 30.0

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Lowercase + word-chars-only tokeniser. No stemming."""
    if not text:
        return []
    return _TOKEN_RE.findall(text.lower())


def keyword_score(query_tokens: list[str], value: str) -> float:
    """Return a 0-1 keyword score for ``value`` against ``query_tokens``.

    Score = fraction of query tokens that appear at least once in the
    tokenised value. Simple, bounded, and monotonic in recall — a value
    that matches every query token scores 1.0, none scores 0.0.
    """
    if not query_tokens:
        return 0.0
    value_tokens = set(tokenize(value))
    if not value_tokens:
        return 0.0
    hits = sum(1 for t in query_tokens if t in value_tokens)
    return hits / len(query_tokens)


def recency_score(
    memory: Memory,
    *,
    now: datetime | None = None,
    half_life_days: float = DEFAULT_RECENCY_HALF_LIFE_DAYS,
) -> float:
    """Return a 0-1 recency score using a true half-life decay.

    Formula: ``2 ** (-age_days / half_life_days)``. A memory exactly
    one half-life old scores 0.5; two half-lives → 0.25; etc. Uses
    ``last_accessed_at`` when set (recall touched the memory), otherwise
    ``updated_at``.
    """
    now = now or datetime.now(timezone.utc)
    ref = memory.last_accessed_at or memory.updated_at
    age_seconds = max(0.0, (now - ref).total_seconds())
    age_days = age_seconds / 86400.0
    return math.pow(2.0, -age_days / half_life_days)


def blend_score(
    *,
    semantic: float,
    keyword: float,
    recency: float,
    w_semantic: float = DEFAULT_W_SEMANTIC,
    w_keyword: float = DEFAULT_W_KEYWORD,
    w_recency: float = DEFAULT_W_RECENCY,
) -> float:
    """Weighted sum, with weights renormalised to sum to 1.0.

    Renormalising lets callers pass any relative weighting (e.g. all
    zeros except `w_keyword=1.0`) without having to do the arithmetic
    themselves. If all weights are zero we fall back to the defaults
    rather than returning an all-zero score.
    """
    total = w_semantic + w_keyword + w_recency
    if total <= 0:
        w_semantic, w_keyword, w_recency = (
            DEFAULT_W_SEMANTIC,
            DEFAULT_W_KEYWORD,
            DEFAULT_W_RECENCY,
        )
        total = 1.0
    ws = w_semantic / total
    wk = w_keyword / total
    wr = w_recency / total
    return ws * semantic + wk * keyword + wr * recency
