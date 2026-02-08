"""Tests for CV generation web routes."""

import pytest


class TestGeneratePreview:
    def test_generate_preview_page(self, seeded_client):
        resp = seeded_client.get("/generate/job-ml-001")
        assert resp.status_code == 200
        assert "Generate CV" in resp.text
        assert "ML Engineer" in resp.text
        assert "Job Description" in resp.text

    def test_generate_preview_not_found(self, seeded_client):
        resp = seeded_client.get("/generate/nonexistent")
        assert resp.status_code == 404

    def test_generate_preview_prefix(self, seeded_client):
        resp = seeded_client.get("/generate/job-ml")
        assert resp.status_code == 200
        assert "ML Engineer" in resp.text


class TestDownload:
    def test_download_nonexistent_job(self, seeded_client):
        resp = seeded_client.get("/generate/nonexistent/download/CV_EN.pdf")
        assert resp.status_code == 404

    def test_download_nonexistent_file(self, seeded_client):
        resp = seeded_client.get("/generate/job-ml-001/download/nope.pdf")
        assert resp.status_code == 404
