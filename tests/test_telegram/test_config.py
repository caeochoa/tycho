"""Tests for TelegramConfig."""

import os
from unittest.mock import patch

from tycho.config import TelegramConfig, TychoConfig, load_config


class TestTelegramConfig:
    def test_defaults(self):
        cfg = TelegramConfig()
        assert cfg.enabled is False
        assert cfg.token == ""
        assert cfg.allowed_users == []
        assert cfg.page_size == 5

    def test_effective_token_from_field(self):
        cfg = TelegramConfig(token="my-token")
        with patch.dict(os.environ, {}, clear=True):
            assert cfg.effective_token == "my-token"

    def test_effective_token_env_overrides_field(self):
        cfg = TelegramConfig(token="my-token")
        with patch.dict(os.environ, {"TYCHO_TELEGRAM_TOKEN": "env-token"}):
            assert cfg.effective_token == "env-token"

    def test_effective_token_empty_env_falls_back(self):
        cfg = TelegramConfig(token="my-token")
        with patch.dict(os.environ, {"TYCHO_TELEGRAM_TOKEN": ""}):
            assert cfg.effective_token == "my-token"

    def test_effective_token_no_env_no_field(self):
        cfg = TelegramConfig()
        with patch.dict(os.environ, {}, clear=True):
            assert cfg.effective_token == ""


class TestTychoConfigTelegram:
    def test_telegram_default(self):
        cfg = TychoConfig()
        assert cfg.telegram.enabled is False
        assert cfg.telegram.token == ""

    def test_telegram_from_dict(self):
        cfg = TychoConfig(telegram={"enabled": True, "token": "abc", "allowed_users": [123], "page_size": 10})
        assert cfg.telegram.enabled is True
        assert cfg.telegram.token == "abc"
        assert cfg.telegram.allowed_users == [123]
        assert cfg.telegram.page_size == 10

    def test_load_config_without_telegram(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("search:\n  terms: ['test']\n")
        cfg = load_config(config_file)
        assert cfg.telegram.enabled is False

    def test_load_config_with_telegram(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("telegram:\n  enabled: true\n  token: file-token\n")
        cfg = load_config(config_file)
        assert cfg.telegram.enabled is True
        assert cfg.telegram.token == "file-token"
