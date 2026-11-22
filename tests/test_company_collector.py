"""Tests for the company careers page collector (ATS adapters)."""

from unittest.mock import MagicMock, patch

import pytest

from tycho.collector.company_collector import (
    PROVIDERS,
    collect_company_jobs,
    detect_provider,
)
from tycho.config import CompanyConfig, TychoConfig


def _response(json_data=None, text=""):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.text = text
    resp.raise_for_status.return_value = None
    return resp


def _fetch_with(provider, board, company, responses):
    """Run a provider fetch with requests.get mocked to return responses in order."""
    with patch("tycho.collector.company_collector.requests.get") as mock_get:
        mock_get.side_effect = responses
        jobs = PROVIDERS[provider].fetch(board, company)
    return jobs, mock_get


class TestDetectProvider:
    @pytest.mark.parametrize(
        "url,provider,board",
        [
            ("https://boards.greenhouse.io/acme", "greenhouse", "acme"),
            ("https://job-boards.greenhouse.io/acme/", "greenhouse", "acme"),
            ("https://boards.eu.greenhouse.io/acme", "greenhouse", "acme"),
            ("https://boards.greenhouse.io/acme/jobs/123", "greenhouse", "acme"),
            ("https://jobs.lever.co/globex", "lever", "globex"),
            ("https://jobs.eu.lever.co/globex", "lever", "globex"),
            ("https://jobs.ashbyhq.com/initech", "ashby", "initech"),
            ("https://apply.workable.com/hooli/", "workable", "hooli"),
            ("https://hooli.workable.com", "workable", "hooli"),
            ("https://careers.smartrecruiters.com/UmbrellaCorp", "smartrecruiters", "UmbrellaCorp"),
            ("https://jobs.smartrecruiters.com/UmbrellaCorp/123-role", "smartrecruiters", "UmbrellaCorp"),
            ("https://wayne.recruitee.com", "recruitee", "wayne"),
            ("https://wayne.recruitee.com/o/batman-engineer", "recruitee", "wayne"),
            ("https://stark.jobs.personio.de", "personio", "stark.jobs.personio.de"),
            ("https://stark.jobs.personio.com/", "personio", "stark.jobs.personio.com"),
        ],
    )
    def test_known_urls(self, url, provider, board):
        assert detect_provider(url) == (provider, board)

    def test_unknown_url_returns_none(self):
        assert detect_provider("https://acme.example.com/careers") is None

    def test_explicit_override_wins(self):
        company = CompanyConfig(
            name="Acme",
            url="https://acme.example.com/careers",
            provider="greenhouse",
            board="acme",
        )
        from tycho.collector.company_collector import resolve_provider

        assert resolve_provider(company) == ("greenhouse", "acme")

    def test_unknown_provider_override_rejected(self):
        company = CompanyConfig(
            name="Acme",
            url="https://acme.example.com/careers",
            provider="notarealats",
            board="acme",
        )
        from tycho.collector.company_collector import resolve_provider

        assert resolve_provider(company) is None


class TestGreenhouseAdapter:
    def test_maps_jobs(self):
        company = CompanyConfig(name="Acme", url="https://boards.greenhouse.io/acme")
        data = {
            "jobs": [
                {
                    "id": 4011,
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/4011",
                    "title": "ML Engineer",
                    "location": {"name": "Madrid, Spain"},
                    "content": "&lt;p&gt;Do ML things&lt;/p&gt;",
                    "first_published": "2026-07-01T10:00:00-04:00",
                    "pay_input_ranges": [
                        {
                            "min_cents": 5000000,
                            "max_cents": 7000000,
                            "currency_type": "EUR",
                            "title": "Madrid",
                        }
                    ],
                }
            ]
        }
        jobs, mock_get = _fetch_with("greenhouse", "acme", company, [_response(data)])

        assert "boards-api.greenhouse.io/v1/boards/acme/jobs" in mock_get.call_args[0][0]
        assert len(jobs) == 1
        job = jobs[0]
        assert job.source == "greenhouse"
        assert job.source_id == "4011"
        assert job.company == "Acme"
        assert job.title == "ML Engineer"
        assert job.location == "Madrid, Spain"
        assert job.description == "Do ML things"
        assert job.url == "https://boards.greenhouse.io/acme/jobs/4011"
        assert job.salary_min == 50000.0
        assert job.salary_max == 70000.0
        assert job.salary_currency == "EUR"
        assert job.salary_interval == "yearly"
        assert job.date_posted is not None

    def test_no_pay_range(self):
        company = CompanyConfig(name="Acme", url="https://boards.greenhouse.io/acme")
        data = {"jobs": [{"id": 1, "title": "Dev", "location": {"name": "Remote"}, "content": ""}]}
        jobs, _ = _fetch_with("greenhouse", "acme", company, [_response(data)])
        assert jobs[0].salary_min is None
        assert jobs[0].salary_currency is None


class TestLeverAdapter:
    def test_maps_jobs(self):
        company = CompanyConfig(name="Globex", url="https://jobs.lever.co/globex")
        data = [
            {
                "id": "abc-123",
                "text": "Backend Engineer",
                "hostedUrl": "https://jobs.lever.co/globex/abc-123",
                "createdAt": 1751364000000,
                "categories": {"location": "London, UK", "commitment": "Full-time"},
                "descriptionPlain": "Build APIs",
                "salaryRange": {"min": 70000, "max": 90000, "currency": "GBP", "interval": "per-year-salary"},
            }
        ]
        jobs, mock_get = _fetch_with("lever", "globex", company, [_response(data)])

        assert "api.lever.co/v0/postings/globex" in mock_get.call_args[0][0]
        job = jobs[0]
        assert job.source == "lever"
        assert job.source_id == "abc-123"
        assert job.title == "Backend Engineer"
        assert job.location == "London, UK"
        assert job.description == "Build APIs"
        assert job.salary_min == 70000.0
        assert job.salary_max == 90000.0
        assert job.salary_currency == "GBP"
        assert job.salary_interval == "yearly"
        assert job.date_posted is not None


class TestAshbyAdapter:
    def test_maps_jobs(self):
        company = CompanyConfig(name="Initech", url="https://jobs.ashbyhq.com/initech")
        data = {
            "jobs": [
                {
                    "id": "uuid-1",
                    "title": "Data Scientist",
                    "location": "Remote",
                    "publishedAt": "2026-06-15T00:00:00.000Z",
                    "jobUrl": "https://jobs.ashbyhq.com/initech/uuid-1",
                    "descriptionHtml": "<p>Stats stuff</p>",
                    "compensation": {
                        "summaryComponents": [
                            {
                                "compensationType": "Salary",
                                "interval": "1 YEAR",
                                "currencyCode": "USD",
                                "minValue": 120000,
                                "maxValue": 150000,
                            }
                        ]
                    },
                }
            ]
        }
        jobs, mock_get = _fetch_with("ashby", "initech", company, [_response(data)])

        assert "api.ashbyhq.com/posting-api/job-board/initech" in mock_get.call_args[0][0]
        job = jobs[0]
        assert job.source == "ashby"
        assert job.title == "Data Scientist"
        assert job.description == "Stats stuff"
        assert job.salary_min == 120000.0
        assert job.salary_currency == "USD"
        assert job.salary_interval == "yearly"


class TestWorkableAdapter:
    def test_maps_jobs(self):
        company = CompanyConfig(name="Hooli", url="https://apply.workable.com/hooli")
        data = {
            "name": "Hooli",
            "jobs": [
                {
                    "title": "Platform Engineer",
                    "shortcode": "ABC123",
                    "country": "Spain",
                    "city": "Madrid",
                    "url": "https://apply.workable.com/hooli/j/ABC123",
                    "published_on": "2026-07-02",
                    "description": "<p>Platforms</p>",
                }
            ],
        }
        jobs, mock_get = _fetch_with("workable", "hooli", company, [_response(data)])

        assert "apply.workable.com/api/v1/widget/accounts/hooli" in mock_get.call_args[0][0]
        job = jobs[0]
        assert job.source == "workable"
        assert job.source_id == "ABC123"
        assert job.location == "Madrid, Spain"
        assert job.description == "Platforms"


class TestSmartRecruitersAdapter:
    def test_maps_jobs_with_detail_fetch(self):
        company = CompanyConfig(name="Umbrella", url="https://careers.smartrecruiters.com/UmbrellaCorp")
        listing = {
            "content": [
                {
                    "id": "744000",
                    "name": "DevOps Engineer",
                    "releasedDate": "2026-06-20T08:00:00.000Z",
                    "location": {"city": "Dublin", "country": "ie"},
                }
            ]
        }
        detail = {
            "jobAd": {
                "sections": {
                    "jobDescription": {"text": "<p>Ops work</p>"},
                    "qualifications": {"text": "<p>K8s</p>"},
                }
            },
            "applyUrl": "https://jobs.smartrecruiters.com/UmbrellaCorp/744000",
        }
        jobs, mock_get = _fetch_with(
            "smartrecruiters", "UmbrellaCorp", company, [_response(listing), _response(detail)]
        )

        assert "api.smartrecruiters.com/v1/companies/UmbrellaCorp/postings" in mock_get.call_args_list[0][0][0]
        job = jobs[0]
        assert job.source == "smartrecruiters"
        assert job.source_id == "744000"
        assert job.title == "DevOps Engineer"
        assert "Dublin" in job.location
        assert "Ops work" in job.description
        assert "K8s" in job.description

    def test_paginates_until_total_found(self):
        company = CompanyConfig(name="Umbrella", url="https://careers.smartrecruiters.com/UmbrellaCorp")
        page1 = {"totalFound": 3, "content": [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]}
        page2 = {"totalFound": 3, "content": [{"id": "3", "name": "C"}]}
        detail = _response({})
        jobs, mock_get = _fetch_with(
            "smartrecruiters", "UmbrellaCorp", company,
            [_response(page1), _response(page2), detail, detail, detail],
        )
        assert [j.source_id for j in jobs] == ["1", "2", "3"]
        assert mock_get.call_args_list[1].kwargs["params"]["offset"] == 2


class TestMissingIds:
    def test_postings_without_id_are_skipped(self):
        company = CompanyConfig(name="Acme", url="https://boards.greenhouse.io/acme")
        data = {"jobs": [{"id": 1, "title": "A"}, {"title": "No id"}]}
        with patch("tycho.collector.company_collector.requests.get") as mock_get:
            mock_get.return_value = _response(data)
            cfg = TychoConfig(companies=[company])
            jobs = collect_company_jobs(cfg)
        assert [j.title for j in jobs] == ["A"]


class TestRecruiteeAdapter:
    def test_maps_jobs(self):
        company = CompanyConfig(name="Wayne", url="https://wayne.recruitee.com")
        data = {
            "offers": [
                {
                    "id": 999,
                    "title": "Frontend Dev",
                    "status": "published",
                    "location": "Amsterdam, Netherlands",
                    "careers_url": "https://wayne.recruitee.com/o/frontend-dev",
                    "description": "<p>React</p>",
                    "requirements": "<p>3 years experience</p>",
                    "salary": {"min": "40000", "max": "50000", "period": "yearly"},
                }
            ]
        }
        jobs, mock_get = _fetch_with("recruitee", "wayne", company, [_response(data)])

        assert "wayne.recruitee.com/api/offers" in mock_get.call_args[0][0]
        job = jobs[0]
        assert job.source == "recruitee"
        assert job.source_id == "999"
        assert job.title == "Frontend Dev"
        assert "React" in job.description
        assert "3 years experience" in job.description
        assert job.salary_min == 40000.0
        assert job.salary_interval == "yearly"


class TestPersonioAdapter:
    def test_maps_jobs_from_xml(self):
        company = CompanyConfig(name="Stark", url="https://stark.jobs.personio.de")
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs>
  <position>
    <id>555</id>
    <office>Berlin</office>
    <department>Engineering</department>
    <name>Site Reliability Engineer</name>
    <jobDescriptions>
      <jobDescription>
        <name>Role</name>
        <value><![CDATA[<p>Keep things up</p>]]></value>
      </jobDescription>
    </jobDescriptions>
  </position>
</workzag-jobs>"""
        jobs, mock_get = _fetch_with(
            "personio", "stark.jobs.personio.de", company, [_response(text=xml)]
        )

        assert "stark.jobs.personio.de/xml" in mock_get.call_args[0][0]
        job = jobs[0]
        assert job.source == "personio"
        assert job.source_id == "555"
        assert job.title == "Site Reliability Engineer"
        assert job.location == "Berlin"
        assert "Keep things up" in job.description
        assert job.url == "https://stark.jobs.personio.de/job/555"


class TestCollectCompanyJobs:
    def test_empty_config_returns_empty(self):
        config = TychoConfig()
        assert collect_company_jobs(config) == []

    def test_disabled_company_skipped(self):
        config = TychoConfig(
            companies=[
                CompanyConfig(name="Acme", url="https://boards.greenhouse.io/acme", enabled=False)
            ]
        )
        with patch("tycho.collector.company_collector.requests.get") as mock_get:
            jobs = collect_company_jobs(config)
        assert jobs == []
        mock_get.assert_not_called()

    def test_unknown_provider_warns_and_continues(self, capsys):
        config = TychoConfig(
            companies=[
                CompanyConfig(name="Mystery", url="https://mystery.example.com/careers"),
                CompanyConfig(name="Acme", url="https://boards.greenhouse.io/acme"),
            ]
        )
        gh_data = {"jobs": [{"id": 1, "title": "Dev", "location": {"name": "Remote"}, "content": ""}]}
        with patch("tycho.collector.company_collector.requests.get", return_value=_response(gh_data)):
            jobs = collect_company_jobs(config)
        assert len(jobs) == 1
        captured = capsys.readouterr()
        assert "Mystery" in captured.out
        assert "greenhouse" in captured.out  # supported providers listed

    def test_one_failing_company_does_not_abort(self, capsys):
        config = TychoConfig(
            companies=[
                CompanyConfig(name="Broken", url="https://jobs.lever.co/broken"),
                CompanyConfig(name="Acme", url="https://boards.greenhouse.io/acme"),
            ]
        )
        gh_data = {"jobs": [{"id": 1, "title": "Dev", "location": {"name": "Remote"}, "content": ""}]}

        def side_effect(url, **kwargs):
            if "lever" in url:
                raise ConnectionError("boom")
            return _response(gh_data)

        with patch("tycho.collector.company_collector.requests.get", side_effect=side_effect):
            jobs = collect_company_jobs(config)
        assert len(jobs) == 1
        assert jobs[0].company == "Acme"
        assert "Broken" in capsys.readouterr().out
