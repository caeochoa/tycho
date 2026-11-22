"""Tests for configuration loading."""

from pathlib import Path

import yaml

from tycho.config import (
    CompanyConfig,
    LLMConfig,
    OutputConfig,
    ScoringConfig,
    ScoringWeights,
    SearchConfig,
    TychoConfig,
    load_config,
)


class TestDefaults:
    def test_search_defaults(self):
        cfg = SearchConfig()
        assert "AI Engineer" in cfg.terms
        assert cfg.country == "Spain"
        assert cfg.results_per_source == 50

    def test_scoring_weights_defaults(self):
        w = ScoringWeights()
        total = w.keyword_match + w.title_match + w.skills_overlap + w.location_match
        assert total == pytest.approx(1.0)

    def test_output_defaults(self):
        cfg = OutputConfig()
        assert cfg.formats == ["pdf"]
        assert cfg.language == "en"

    def test_llm_defaults(self):
        cfg = LLMConfig()
        assert cfg.provider == "anthropic"
        assert cfg.temperature == 0.3

    def test_search_max_age_days_default(self):
        cfg = SearchConfig()
        assert cfg.max_age_days == 30

    def test_recency_defaults(self):
        cfg = ScoringConfig()
        assert cfg.recency.enabled is True
        assert cfg.recency.full_score_days == 14
        assert cfg.recency.decay_days == 90
        assert cfg.recency.min_factor == 0.4


class TestLoadConfig:
    def test_missing_file_returns_defaults(self, tmp_path):
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert isinstance(cfg, TychoConfig)
        assert cfg.search.country == "Spain"

    def test_empty_file_returns_defaults(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")
        cfg = load_config(config_path)
        assert isinstance(cfg, TychoConfig)

    def test_partial_config(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump({"search": {"country": "UK"}}))
        cfg = load_config(config_path)
        assert cfg.search.country == "UK"
        # Other fields should still have defaults
        assert cfg.output.language == "en"
        assert cfg.scoring.weights.keyword_match == 0.35

    def test_full_config(self, tmp_path):
        data = {
            "search": {
                "terms": ["Data Engineer"],
                "locations": ["Berlin"],
                "country": "Germany",
                "results_per_source": 25,
            },
            "output": {"formats": ["pdf", "tex"], "language": "es"},
            "db_path": "custom.db",
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(data))
        cfg = load_config(config_path)
        assert cfg.search.terms == ["Data Engineer"]
        assert cfg.search.country == "Germany"
        assert cfg.output.formats == ["pdf", "tex"]
        assert cfg.db_path == "custom.db"

    def test_companies_default_empty(self, tmp_path):
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg.companies == []

    def test_companies_from_yaml(self, tmp_path):
        data = {
            "companies": [
                {"name": "Acme", "url": "https://boards.greenhouse.io/acme"},
                {
                    "name": "Globex",
                    "url": "https://globex.example.com/careers",
                    "provider": "lever",
                    "board": "globex",
                    "enabled": False,
                },
            ]
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(data))
        cfg = load_config(config_path)
        assert len(cfg.companies) == 2
        acme = cfg.companies[0]
        assert isinstance(acme, CompanyConfig)
        assert acme.name == "Acme"
        assert acme.url == "https://boards.greenhouse.io/acme"
        assert acme.provider is None
        assert acme.board is None
        assert acme.enabled is True
        globex = cfg.companies[1]
        assert globex.provider == "lever"
        assert globex.board == "globex"
        assert globex.enabled is False

    def test_max_age_days_and_recency_from_yaml(self, tmp_path):
        data = {
            "search": {"max_age_days": 7},
            "scoring": {"recency": {"enabled": False, "min_factor": 0.2}},
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(data))
        cfg = load_config(config_path)
        assert cfg.search.max_age_days == 7
        assert cfg.scoring.recency.enabled is False
        assert cfg.scoring.recency.min_factor == 0.2
        # Unset recency fields keep defaults
        assert cfg.scoring.recency.full_score_days == 14

    def test_none_path_uses_default(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        # No config.yaml exists → defaults
        cfg = load_config(None)
        assert isinstance(cfg, TychoConfig)


# Need this import for approx
import pytest


def test_min_keywords_confidence_must_be_positive():
    import pytest
    from pydantic import ValidationError
    from tycho.config import ScoringConfig
    with pytest.raises(ValidationError):
        ScoringConfig(min_keywords_confidence=0)
