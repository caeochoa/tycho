"""Tests for defensive date parsing."""

from datetime import datetime

import pytest

from tycho.collector.parsing import parse_date
from tycho.timeutils import age_days


@pytest.mark.parametrize("raw", [
    "2025-01-10T09:00:00-05:00",
    "2024-05-01T10:00:00Z",
    "2024-05-01 10:12:33 UTC",
])
def test_parse_date_returns_naive_and_age_computable(raw):
    dt = parse_date(raw)
    assert dt is not None and dt.tzinfo is None
    assert age_days(dt) > 0


def test_parse_date_aware_datetime_made_naive():
    from datetime import timezone
    assert parse_date(datetime(2025, 1, 1, tzinfo=timezone.utc)).tzinfo is None


def test_parse_date_garbage_is_none():
    assert parse_date("not a date") is None
