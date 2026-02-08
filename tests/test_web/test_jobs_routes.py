"""Tests for job listing and detail web routes."""

import pytest


class TestJobList:
    def test_index_redirects_to_jobs(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/jobs"

    def test_empty_job_list(self, client):
        resp = client.get("/jobs")
        assert resp.status_code == 200
        assert "No jobs found" in resp.text

    def test_job_list_shows_jobs(self, seeded_client):
        resp = seeded_client.get("/jobs")
        assert resp.status_code == 200
        assert "ML Engineer" in resp.text
        assert "Backend Developer" in resp.text
        assert "Data Scientist" in resp.text

    def test_filter_by_status(self, seeded_client):
        resp = seeded_client.get("/jobs?status=interested")
        assert resp.status_code == 200
        assert "Backend Developer" in resp.text
        assert "ML Engineer" not in resp.text

    def test_filter_by_min_score(self, seeded_client):
        resp = seeded_client.get("/jobs?min_score=0.7")
        assert resp.status_code == 200
        assert "ML Engineer" in resp.text
        assert "Data Scientist" not in resp.text

    def test_search_filter(self, seeded_client):
        resp = seeded_client.get("/jobs?search=DeepTech")
        assert resp.status_code == 200
        assert "ML Engineer" in resp.text
        assert "Backend Developer" not in resp.text

    def test_pagination_params_accepted(self, seeded_client):
        resp = seeded_client.get("/jobs?per_page=5&page=1")
        assert resp.status_code == 200
        # With 3 jobs and per_page=5, all fit on one page
        assert "ML Engineer" in resp.text

    def test_htmx_returns_partial(self, seeded_client):
        resp = seeded_client.get("/jobs", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        # Partial should not include <html> or <nav>
        assert "<nav" not in resp.text
        assert "<table" in resp.text


class TestJobDetail:
    def test_job_detail(self, seeded_client):
        resp = seeded_client.get("/jobs/job-ml-001")
        assert resp.status_code == 200
        assert "ML Engineer" in resp.text
        assert "DeepTech AI" in resp.text
        assert "Madrid" in resp.text

    def test_job_detail_prefix_match(self, seeded_client):
        resp = seeded_client.get("/jobs/job-ml")
        assert resp.status_code == 200
        assert "ML Engineer" in resp.text

    def test_job_detail_not_found(self, seeded_client):
        resp = seeded_client.get("/jobs/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.text.lower() or "Not Found" in resp.text

    def test_job_detail_score_breakdown(self, seeded_client):
        resp = seeded_client.get("/jobs/job-ml-001")
        assert resp.status_code == 200
        assert "Keyword Match" in resp.text
        assert "0.850" in resp.text or "0.85" in resp.text


class TestStatusUpdate:
    def test_inline_status_update(self, seeded_client):
        resp = seeded_client.post(
            "/jobs/job-ml-001/status",
            data={"new_status": "interested"},
        )
        assert resp.status_code == 200
        assert "interested" in resp.text

    def test_status_update_not_found(self, seeded_client):
        resp = seeded_client.post(
            "/jobs/nonexistent/status",
            data={"new_status": "interested"},
        )
        assert resp.status_code == 404

    def test_bulk_status_update(self, seeded_client):
        resp = seeded_client.post(
            "/jobs/bulk-status",
            data={"new_status": "reviewed", "job_ids": ["job-ml-001", "job-ds-003"]},
        )
        assert resp.status_code == 200
