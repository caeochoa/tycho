"""Configuration loading via Pydantic settings."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SearchConfig(BaseModel):
    terms: list[str] = ["AI Engineer", "Machine Learning Engineer"]
    locations: list[str] = ["Remote", "Madrid"]
    country: str = "Spain"
    location_countries: dict[str, str] = {}
    linkedin_fetch_description: bool = True
    results_per_source: int = 50
    max_age_days: int | None = 30  # Only collect postings this recent; None/0 disables


class ScoringWeights(BaseModel):
    keyword_match: float = 0.25
    title_match: float = 0.20
    skills_overlap: float = 0.40
    location_match: float = 0.15


class ScoringThresholds(BaseModel):
    high_interest: float = 0.75
    low_interest: float = 0.25


class LocationConfig(BaseModel):
    preferred: list[str] = ["madrid", "london", "edinburgh", "spain", "uk"]
    preferred_es: list[str] = ["españa", "reino unido", "edimburgo", "londres"]
    remote_keywords: list[str] = ["remote", "remoto"]
    abbreviations: dict[str, str] = Field(default_factory=dict)


class RecencyConfig(BaseModel):
    """Score decay for old postings so stale jobs sink in the ranking."""
    enabled: bool = True
    full_score_days: int = 14   # No penalty up to this age
    decay_days: int = 90        # Age at which the factor bottoms out
    min_factor: float = 0.4     # Score multiplier floor


class ScoringConfig(BaseModel):
    weights: ScoringWeights = ScoringWeights()
    thresholds: ScoringThresholds = ScoringThresholds()
    locations: LocationConfig = LocationConfig()
    recency: RecencyConfig = RecencyConfig()
    min_keywords_confidence: int = Field(default=8, ge=1)  # Keyword count required for full keyword_match confidence


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-5-20250929"
    temperature: float = 0.3
    enabled: bool = True
    base_url: str | None = None


class CoverLetterConfig(BaseModel):
    max_paragraphs: int = 3
    tone: str = "professional"


class OutputConfig(BaseModel):
    formats: list[str] = ["pdf"]
    language: str = "en"
    template: str = "ats_resume"


class WebConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False


class SchedulerConfig(BaseModel):
    enabled: bool = False
    cron: str = "0 8 * * *"  # Daily at 8 AM


class CompanyConfig(BaseModel):
    """A company careers page to monitor directly (ATS-hosted job board)."""
    name: str                    # display name; used as Job.company
    url: str                     # careers page / job board URL
    provider: str | None = None  # override auto-detection ("greenhouse", "lever", ...)
    board: str | None = None     # override board slug extracted from the URL
    enabled: bool = True


class TelegramConfig(BaseModel):
    enabled: bool = False
    token: str = ""
    allowed_users: list[int] = Field(default_factory=list)
    page_size: int = 5

    @property
    def effective_token(self) -> str:
        return os.getenv("TYCHO_TELEGRAM_TOKEN", "") or self.token


class TychoConfig(BaseModel):
    search: SearchConfig = SearchConfig()
    scoring: ScoringConfig = ScoringConfig()
    llm: LLMConfig = LLMConfig()
    cover_letter: CoverLetterConfig = CoverLetterConfig()
    output: OutputConfig = OutputConfig()
    web: WebConfig = WebConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    telegram: TelegramConfig = TelegramConfig()
    companies: list[CompanyConfig] = Field(default_factory=list)
    profile_dir: str = "profile"
    db_path: str = "tycho.db"
    output_dir: str = "output"


def load_config(config_path: Path | None = None) -> TychoConfig:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path("config.yaml")

    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return TychoConfig(**data)

    return TychoConfig()
