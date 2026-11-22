"""Company careers page collector via ATS provider APIs.

Most company careers pages are hosted by an ATS (Greenhouse, Lever, Ashby, ...)
that exposes a public JSON API. Adding a company is one entry in config.yaml:

    companies:
      - name: Acme
        url: https://boards.greenhouse.io/acme

The provider and board slug are auto-detected from the URL; `provider:` and
`board:` keys override detection for unusual setups. Adding a new ATS is one
`Provider` entry in PROVIDERS: URL regexes + a fetch function.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import requests

from tycho.collector.base import BaseCollector
from tycho.collector.parsing import parse_date, parse_float
from tycho.config import CompanyConfig
from tycho.models import Job, JobStatus

REQUEST_TIMEOUT = 20
HEADERS = {"User-Agent": "tycho-job-collector"}


def _strip_html(html: str) -> str:
    """Convert an HTML (possibly entity-escaped) description to plain text."""
    if not html:
        return ""
    from html import unescape

    from bs4 import BeautifulSoup

    text = unescape(html)
    if "<" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    return text.strip()


def _make_job(
    company: CompanyConfig,
    provider: str,
    source_id: str,
    title: str,
    location: str = "",
    description: str = "",
    url: str = "",
    salary_min: float | None = None,
    salary_max: float | None = None,
    salary_currency: str | None = None,
    salary_interval: str | None = None,
    date_posted: datetime | None = None,
) -> Job:
    return Job(
        id=str(uuid.uuid4()),
        source=provider,
        source_id=str(source_id),
        title=title,
        company=company.name,
        location=location,
        description=description,
        url=url,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        salary_interval=salary_interval,
        date_posted=date_posted,
        date_collected=datetime.now(),
        status=JobStatus.NEW,
    )


def _get_json(url: str, **kwargs):
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, **kwargs)
    resp.raise_for_status()
    return resp.json()


# --- Provider registry ---

@dataclass
class Provider:
    name: str
    url_patterns: list[re.Pattern]  # first capture group = board slug
    fetch: Callable[[str, CompanyConfig], list[Job]]


def _normalize_interval(raw) -> str | None:
    """Map provider-specific pay intervals to jobspy's vocabulary."""
    if not raw:
        return None
    s = str(raw).lower()
    for key, norm in (
        ("year", "yearly"),
        ("annual", "yearly"),
        ("month", "monthly"),
        ("week", "weekly"),
        ("day", "daily"),
        ("hour", "hourly"),
    ):
        if key in s:
            return norm
    return None


def _fetch_greenhouse(board: str, company: CompanyConfig) -> list[Job]:
    data = _get_json(
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
        params={"content": "true"},
    )
    jobs = []
    for item in data.get("jobs", []):
        salary_min = salary_max = None
        currency = interval = None
        pay_ranges = item.get("pay_input_ranges") or []
        if pay_ranges:
            rng = pay_ranges[0]
            salary_min = parse_float(rng.get("min_cents"))
            salary_max = parse_float(rng.get("max_cents"))
            salary_min = salary_min / 100 if salary_min is not None else None
            salary_max = salary_max / 100 if salary_max is not None else None
            currency = rng.get("currency_type") or None
            interval = "yearly"  # Greenhouse pay ranges are annual
        jobs.append(
            _make_job(
                company,
                "greenhouse",
                source_id=item.get("id", ""),
                title=item.get("title", ""),
                location=(item.get("location") or {}).get("name", ""),
                description=_strip_html(item.get("content", "")),
                url=item.get("absolute_url", ""),
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=currency,
                salary_interval=interval,
                date_posted=parse_date(item.get("first_published") or item.get("updated_at")),
            )
        )
    return jobs


def _fetch_lever(board: str, company: CompanyConfig) -> list[Job]:
    data = _get_json(f"https://api.lever.co/v0/postings/{board}", params={"mode": "json"})
    jobs = []
    for item in data:
        salary = item.get("salaryRange") or {}
        created_ms = item.get("createdAt")
        date_posted = (
            datetime.fromtimestamp(created_ms / 1000) if created_ms else None
        )
        jobs.append(
            _make_job(
                company,
                "lever",
                source_id=item.get("id", ""),
                title=item.get("text", ""),
                location=(item.get("categories") or {}).get("location", "") or "",
                description=item.get("descriptionPlain") or _strip_html(item.get("description", "")),
                url=item.get("hostedUrl", ""),
                salary_min=parse_float(salary.get("min")),
                salary_max=parse_float(salary.get("max")),
                salary_currency=salary.get("currency") or None,
                salary_interval=_normalize_interval(salary.get("interval")),
                date_posted=date_posted,
            )
        )
    return jobs


def _fetch_ashby(board: str, company: CompanyConfig) -> list[Job]:
    data = _get_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{board}",
        params={"includeCompensation": "true"},
    )
    jobs = []
    for item in data.get("jobs", []):
        salary_min = salary_max = None
        currency = interval = None
        components = (item.get("compensation") or {}).get("summaryComponents") or []
        for comp in components:
            if str(comp.get("compensationType", "")).lower() == "salary":
                salary_min = parse_float(comp.get("minValue"))
                salary_max = parse_float(comp.get("maxValue"))
                currency = comp.get("currencyCode") or None
                interval = _normalize_interval(comp.get("interval"))
                break
        description = item.get("descriptionPlain") or _strip_html(item.get("descriptionHtml", ""))
        jobs.append(
            _make_job(
                company,
                "ashby",
                source_id=item.get("id", ""),
                title=item.get("title", ""),
                location=item.get("location", "") or "",
                description=description,
                url=item.get("jobUrl") or item.get("applyUrl", ""),
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=currency,
                salary_interval=interval,
                date_posted=parse_date(item.get("publishedAt")),
            )
        )
    return jobs


def _fetch_workable(board: str, company: CompanyConfig) -> list[Job]:
    data = _get_json(
        f"https://apply.workable.com/api/v1/widget/accounts/{board}",
        params={"details": "true"},
    )
    jobs = []
    for item in data.get("jobs", []):
        location = ", ".join(p for p in (item.get("city"), item.get("country")) if p)
        jobs.append(
            _make_job(
                company,
                "workable",
                source_id=item.get("shortcode") or item.get("code", ""),
                title=item.get("title", ""),
                location=location,
                description=_strip_html(item.get("description", "")),
                url=item.get("url") or item.get("application_url", ""),
                date_posted=parse_date(item.get("published_on")),
            )
        )
    return jobs


def _fetch_smartrecruiters(board: str, company: CompanyConfig) -> list[Job]:
    page_size = 100
    items: list[dict] = []
    while True:
        data = _get_json(
            f"https://api.smartrecruiters.com/v1/companies/{board}/postings",
            params={"limit": page_size, "offset": len(items)},
        )
        page = data.get("content", [])
        items.extend(page)
        if not page or len(items) >= (data.get("totalFound") or 0):
            break
    jobs = []
    for item in items:
        posting_id = item.get("id", "")
        loc = item.get("location") or {}
        location = ", ".join(p for p in (loc.get("city"), loc.get("country")) if p)
        description = ""
        url = f"https://jobs.smartrecruiters.com/{board}/{posting_id}"
        # The listing endpoint has no description; fetch the posting detail.
        try:
            detail = _get_json(
                f"https://api.smartrecruiters.com/v1/companies/{board}/postings/{posting_id}"
            )
            sections = (detail.get("jobAd") or {}).get("sections") or {}
            description = " ".join(
                _strip_html(section.get("text", ""))
                for section in sections.values()
                if isinstance(section, dict) and section.get("text")
            ).strip()
            url = detail.get("applyUrl") or url
        except Exception:
            pass
        jobs.append(
            _make_job(
                company,
                "smartrecruiters",
                source_id=posting_id,
                title=item.get("name", ""),
                location=location,
                description=description,
                url=url,
                date_posted=parse_date(item.get("releasedDate")),
            )
        )
    return jobs


def _fetch_recruitee(board: str, company: CompanyConfig) -> list[Job]:
    data = _get_json(f"https://{board}.recruitee.com/api/offers/")
    jobs = []
    for item in data.get("offers", []):
        salary = item.get("salary") or {}
        description = " ".join(
            _strip_html(item.get(field, "")) for field in ("description", "requirements")
        ).strip()
        jobs.append(
            _make_job(
                company,
                "recruitee",
                source_id=item.get("id", ""),
                title=item.get("title", ""),
                location=item.get("location", "") or "",
                description=description,
                url=item.get("careers_url", ""),
                salary_min=parse_float(salary.get("min")),
                salary_max=parse_float(salary.get("max")),
                salary_currency=salary.get("currency") or None,
                salary_interval=_normalize_interval(salary.get("period")),
                date_posted=parse_date(item.get("created_at")),
            )
        )
    return jobs


def _fetch_personio(board: str, company: CompanyConfig) -> list[Job]:
    import xml.etree.ElementTree as ET

    resp = requests.get(f"https://{board}/xml", headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    jobs = []
    for position in root.iter("position"):
        def _text(tag: str) -> str:
            el = position.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""

        job_id = _text("id")
        description = " ".join(
            _strip_html(value.text or "")
            for value in position.findall("./jobDescriptions/jobDescription/value")
        ).strip()
        jobs.append(
            _make_job(
                company,
                "personio",
                source_id=job_id,
                title=_text("name"),
                location=_text("office"),
                description=description,
                url=f"https://{board}/job/{job_id}",
            )
        )
    return jobs


PROVIDERS: dict[str, Provider] = {
    "greenhouse": Provider(
        name="greenhouse",
        url_patterns=[
            re.compile(r"https?://(?:job-)?boards(?:\.eu)?\.greenhouse\.io/([^/?#]+)"),
        ],
        fetch=_fetch_greenhouse,
    ),
    "lever": Provider(
        name="lever",
        url_patterns=[
            re.compile(r"https?://jobs(?:\.eu)?\.lever\.co/([^/?#]+)"),
        ],
        fetch=_fetch_lever,
    ),
    "ashby": Provider(
        name="ashby",
        url_patterns=[
            re.compile(r"https?://jobs\.ashbyhq\.com/([^/?#]+)"),
        ],
        fetch=_fetch_ashby,
    ),
    "workable": Provider(
        name="workable",
        url_patterns=[
            re.compile(r"https?://apply\.workable\.com/([^/?#]+)"),
            re.compile(r"https?://([^./]+)\.workable\.com"),
        ],
        fetch=_fetch_workable,
    ),
    "smartrecruiters": Provider(
        name="smartrecruiters",
        url_patterns=[
            re.compile(r"https?://(?:careers|jobs)\.smartrecruiters\.com/([^/?#]+)"),
        ],
        fetch=_fetch_smartrecruiters,
    ),
    "recruitee": Provider(
        name="recruitee",
        url_patterns=[
            re.compile(r"https?://([^./]+)\.recruitee\.com"),
        ],
        fetch=_fetch_recruitee,
    ),
    "personio": Provider(
        name="personio",
        # Personio boards live on their own subdomain; the board "slug" is the
        # full host so the fetcher can hit https://{host}/xml directly.
        url_patterns=[
            re.compile(r"https?://([^/?#]+\.jobs\.personio\.(?:de|com))"),
        ],
        fetch=_fetch_personio,
    ),
}


def detect_provider(url: str) -> tuple[str, str] | None:
    """Detect (provider, board slug) from a careers page URL."""
    for provider in PROVIDERS.values():
        for pattern in provider.url_patterns:
            match = pattern.match(url)
            if match:
                return provider.name, match.group(1)
    return None


def resolve_provider(company: CompanyConfig) -> tuple[str, str] | None:
    """Resolve (provider, board) for a company, honoring config overrides."""
    if company.provider:
        if company.provider not in PROVIDERS:
            return None
        board = company.board
        if not board:
            detected = detect_provider(company.url)
            board = detected[1] if detected else None
        if not board:
            return None
        return company.provider, board
    detected = detect_provider(company.url)
    if detected and company.board:
        return detected[0], company.board
    return detected


class CompanyCollector(BaseCollector):
    """Collect all postings from configured companies' ATS job boards.

    Search terms and locations are ignored: company boards are small, so every
    posting is collected and the scorer ranks them.
    """

    def __init__(self, companies: list[CompanyConfig]):
        self.companies = companies

    def collect(
        self,
        search_terms: list[str] | None = None,
        locations: list[str] | None = None,
        results_wanted: int = 50,
    ) -> list[Job]:
        all_jobs: list[Job] = []
        for company in self.companies:
            if not company.enabled:
                continue
            resolved = resolve_provider(company)
            if resolved is None:
                supported = ", ".join(sorted(PROVIDERS))
                print(
                    f"  [warning] '{company.name}': could not detect ATS provider from "
                    f"{company.url} (supported: {supported}). "
                    f"Set 'provider:' and 'board:' explicitly in config.yaml."
                )
                continue
            provider_name, board = resolved
            try:
                jobs = PROVIDERS[provider_name].fetch(board, company)
                missing = [j for j in jobs if not j.source_id]
                if missing:
                    print(f"  [warning] {company.name}: skipping {len(missing)} posting(s) without an id")
                    jobs = [j for j in jobs if j.source_id]
                print(f"  {company.name} ({provider_name}): {len(jobs)} jobs")
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"  [warning] Failed to collect '{company.name}' via {provider_name}: {e}")
        return all_jobs


def collect_company_jobs(config) -> list[Job]:
    """Collect from all enabled configured companies; empty list if none configured."""
    if not config.companies:
        return []
    return CompanyCollector(config.companies).collect()
