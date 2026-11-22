"""Tests for age helpers used by scoring, CLI, and web display."""

from datetime import datetime, timedelta

import pytest

from tycho.timeutils import age_days, age_label


class TestAgeDays:
    def test_days_since_date(self):
        dt = datetime.now() - timedelta(days=10)
        assert age_days(dt) == pytest.approx(10.0, abs=0.01)

    def test_uses_fallback_when_primary_none(self):
        fallback = datetime.now() - timedelta(days=5)
        assert age_days(None, fallback=fallback) == pytest.approx(5.0, abs=0.01)

    def test_primary_wins_over_fallback(self):
        primary = datetime.now() - timedelta(days=3)
        fallback = datetime.now() - timedelta(days=30)
        assert age_days(primary, fallback=fallback) == pytest.approx(3.0, abs=0.01)

    def test_none_when_no_dates(self):
        assert age_days(None) is None
        assert age_days(None, fallback=None) is None

    def test_future_date_clamped_to_zero(self):
        dt = datetime.now() + timedelta(days=2)
        assert age_days(dt) == 0.0


class TestAgeLabel:
    def test_none_is_dash(self):
        assert age_label(None) == "—"

    def test_today(self):
        assert age_label(datetime.now()) == "0d"

    def test_days(self):
        assert age_label(datetime.now() - timedelta(days=3)) == "3d"

    def test_weeks(self):
        assert age_label(datetime.now() - timedelta(days=10)) == "1w"
        assert age_label(datetime.now() - timedelta(days=20)) == "2w"

    def test_months(self):
        assert age_label(datetime.now() - timedelta(days=45)) == "1mo"
        assert age_label(datetime.now() - timedelta(days=150)) == "5mo"

    def test_years(self):
        assert age_label(datetime.now() - timedelta(days=400)) == "1y"
        assert age_label(datetime.now() - timedelta(days=800)) == "2y"
