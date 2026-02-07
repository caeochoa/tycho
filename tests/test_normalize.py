"""Tests for job normalization and deduplication."""

from tycho.collector.normalize import (
    dedup_key,
    deduplicate,
    normalize_company,
    normalize_text,
)
from tycho.models import Job


class TestNormalizeText:
    def test_basic(self):
        assert normalize_text("  Hello World  ") == "hello world"

    def test_collapse_whitespace(self):
        assert normalize_text("a   b\t\nc") == "a b c"

    def test_empty(self):
        assert normalize_text("") == ""

    def test_mixed_case(self):
        assert normalize_text("PyTorch ONNX cuda") == "pytorch onnx cuda"


class TestNormalizeCompany:
    def test_basic(self):
        assert normalize_company("Google") == "google"

    def test_suffix_removal(self):
        assert normalize_company("Acme Inc.") == "acme"
        assert normalize_company("Acme Inc") == "acme"
        assert normalize_company("Acme Ltd") == "acme"
        assert normalize_company("Acme Ltd.") == "acme"
        assert normalize_company("Acme LLC") == "acme"
        assert normalize_company("Empresa S.A.") == "empresa"
        assert normalize_company("Empresa S.L.") == "empresa"
        assert normalize_company("Firma GmbH") == "firma"
        assert normalize_company("Corp PLC") == "corp"

    def test_no_suffix(self):
        assert normalize_company("Google") == "google"
        assert normalize_company("Grupo Oesía") == "grupo oesía"

    def test_whitespace(self):
        assert normalize_company("  Acme  Corp  Ltd  ") == "acme corp"


class TestDedupKey:
    def test_deterministic(self):
        job = Job(id="1", source="indeed", title="ML Engineer", company="Google", location="Madrid")
        key1 = dedup_key(job)
        key2 = dedup_key(job)
        assert key1 == key2

    def test_case_insensitive(self):
        job1 = Job(id="1", source="indeed", title="ML Engineer", company="Google", location="Madrid")
        job2 = Job(id="2", source="linkedin", title="ml engineer", company="google", location="madrid")
        assert dedup_key(job1) == dedup_key(job2)

    def test_different_jobs_different_keys(self):
        job1 = Job(id="1", source="indeed", title="ML Engineer", company="Google", location="Madrid")
        job2 = Job(id="2", source="indeed", title="Data Engineer", company="Google", location="Madrid")
        assert dedup_key(job1) != dedup_key(job2)

    def test_suffix_normalized(self):
        job1 = Job(id="1", source="indeed", title="Dev", company="Acme Ltd", location="London")
        job2 = Job(id="2", source="indeed", title="Dev", company="Acme", location="London")
        assert dedup_key(job1) == dedup_key(job2)


class TestDeduplicate:
    def test_empty(self):
        assert deduplicate([]) == []

    def test_single_job(self):
        job = Job(id="1", source="indeed", title="Dev", company="Corp", location="Madrid")
        result = deduplicate([job])
        assert len(result) == 1
        assert result[0].id == "1"

    def test_no_duplicates(self):
        jobs = [
            Job(id="1", source="indeed", title="ML Engineer", company="Google", location="Madrid"),
            Job(id="2", source="indeed", title="Data Engineer", company="Amazon", location="London"),
        ]
        result = deduplicate(jobs)
        assert len(result) == 2

    def test_duplicate_keeps_longer_description(self):
        jobs = [
            Job(id="1", source="indeed", title="Dev", company="Corp", location="Madrid", description="Short"),
            Job(id="2", source="linkedin", title="Dev", company="Corp", location="Madrid", description="Much longer description here"),
        ]
        result = deduplicate(jobs)
        assert len(result) == 1
        assert "longer" in result[0].description
        # Preserves first job's ID
        assert result[0].id == "1"

    def test_duplicate_keeps_first_if_equal_length(self):
        jobs = [
            Job(id="1", source="indeed", title="Dev", company="Corp", location="Madrid", description="AAAA"),
            Job(id="2", source="linkedin", title="Dev", company="Corp", location="Madrid", description="BBBB"),
        ]
        result = deduplicate(jobs)
        assert len(result) == 1
        assert result[0].description == "AAAA"

    def test_multiple_duplicates(self):
        jobs = [
            Job(id="1", source="indeed", title="Dev", company="Corp", location="Madrid"),
            Job(id="2", source="linkedin", title="Dev", company="Corp", location="Madrid"),
            Job(id="3", source="indeed", title="Dev", company="Corp", location="Madrid"),
        ]
        result = deduplicate(jobs)
        assert len(result) == 1
