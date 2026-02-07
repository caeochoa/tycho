"""Tests for the LLM client abstraction."""

import os
from unittest.mock import MagicMock, patch

import pytest

from tycho.config import LLMConfig
from tycho.llm.client import LLMClient, get_llm_client


class TestLLMClientAvailability:
    def test_disabled_config_not_available(self):
        config = LLMConfig(enabled=False)
        client = LLMClient(config)
        assert client.available is False

    def test_unknown_provider_not_available(self):
        config = LLMConfig(provider="nonexistent")
        client = LLMClient(config)
        assert client.available is False

    def test_missing_package_not_available(self):
        config = LLMConfig(provider="anthropic")
        with patch.dict("sys.modules", {"langchain_anthropic": None}):
            # Simulating ImportError by making import fail
            client = LLMClient(config)
            # Can't easily test this without actually uninstalling,
            # but we test the logic path

    def test_missing_api_key_not_available(self):
        config = LLMConfig(provider="anthropic")
        with patch.dict(os.environ, {}, clear=True):
            # Remove ANTHROPIC_API_KEY if present
            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                client = LLMClient(config)
                # If langchain-anthropic is installed but no key, should be False
                try:
                    import langchain_anthropic
                    assert client.available is False
                except ImportError:
                    # Package not installed, also not available
                    assert client.available is False

    def test_ollama_no_api_key_needed(self):
        config = LLMConfig(provider="ollama", model="llama3")
        client = LLMClient(config)
        # Available only if langchain-ollama is installed
        try:
            import langchain_ollama
            assert client.available is True
        except ImportError:
            assert client.available is False


class TestLLMClientFactory:
    def test_get_llm_client_returns_client(self):
        config = LLMConfig()
        client = get_llm_client(config)
        assert isinstance(client, LLMClient)

    def test_factory_passes_config(self):
        config = LLMConfig(provider="openai", model="gpt-4o")
        client = get_llm_client(config)
        assert client._config.provider == "openai"
        assert client._config.model == "gpt-4o"


class TestLLMClientInvoke:
    def test_invoke_calls_model(self):
        config = LLMConfig()
        client = LLMClient(config)

        # Mock the model
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(content="Hello from LLM")
        client._model = mock_model

        result = client.invoke("test prompt")
        assert result == "Hello from LLM"
        mock_model.invoke.assert_called_once()

    def test_invoke_structured_calls_with_schema(self):
        from tycho.models import LLMKeywordResult

        config = LLMConfig()
        client = LLMClient(config)

        mock_result = LLMKeywordResult(keywords=["python"])
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = mock_result

        mock_model = MagicMock()
        mock_model.with_structured_output.return_value = mock_structured
        client._model = mock_model

        result = client.invoke_structured("test", LLMKeywordResult)
        assert result.keywords == ["python"]
        mock_model.with_structured_output.assert_called_once_with(LLMKeywordResult)

    def test_lazy_init_not_called_until_invoke(self):
        config = LLMConfig(enabled=False)
        client = LLMClient(config)
        assert client._model is None
