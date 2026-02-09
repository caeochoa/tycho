"""Configuration loading via Pydantic settings."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SearchConfig(BaseModel):
    terms: list[str] = ["AI Engineer", "Machine Learning Engineer"]
    locations: list[str] = ["Remote", "Madrid"]
    country: str = "Spain"
    results_per_source: int = 50


class ScoringWeights(BaseModel):
    keyword_match: float = 0.35
    title_match: float = 0.25
    skills_overlap: float = 0.25
    location_match: float = 0.15


class ScoringThresholds(BaseModel):
    high_interest: float = 0.75
    low_interest: float = 0.30


class LocationConfig(BaseModel):
    preferred: list[str] = ["madrid", "london", "edinburgh", "spain", "uk"]
    preferred_es: list[str] = ["españa", "reino unido", "edimburgo", "londres"]
    remote_keywords: list[str] = ["remote", "remoto"]
    abbreviations: dict[str, str] = Field(default_factory=dict)


class ScoringConfig(BaseModel):
    weights: ScoringWeights = ScoringWeights()
    thresholds: ScoringThresholds = ScoringThresholds()
    locations: LocationConfig = LocationConfig()


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
