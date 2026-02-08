"""Tests for schedule web routes."""

import pytest


class TestScheduleIndex:
    def test_schedule_page_loads(self, client):
        resp = client.get("/schedule")
        assert resp.status_code == 200
        assert "Schedule" in resp.text
        assert "Inactive" in resp.text  # scheduler not enabled in test config

    def test_schedule_status_partial(self, client):
        resp = client.get("/schedule/status")
        assert resp.status_code == 200


class TestScheduleTrigger:
    def test_trigger_without_collector(self, client):
        # This will attempt to run collection, which may fail without network
        # but should not crash the server
        resp = client.post("/schedule/trigger")
        assert resp.status_code == 200
        assert "triggered" in resp.text.lower() or "Status" in resp.text
