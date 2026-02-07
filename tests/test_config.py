"""Tests for configuration loading."""

from pathlib import Path

import yaml

from tycho.config import (
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

    def test_none_path_uses_default(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        # No config.yaml exists → defaults
        cfg = load_config(None)
        assert isinstance(cfg, TychoConfig)


# Need this import for approx
import pytest
