"""LLM client abstraction wrapping LangChain providers."""

from __future__ import annotations

import logging
import os

from pydantic import BaseModel

from tycho.config import LLMConfig

logger = logging.getLogger(__name__)

# Map provider names to their LangChain module and class, plus env var for API key
_PROVIDER_MAP = {
    "anthropic": {
        "module": "langchain_anthropic",
        "class": "ChatAnthropic",
        "env_key": "ANTHROPIC_API_KEY",
    },
    "openai": {
        "module": "langchain_openai",
        "class": "ChatOpenAI",
        "env_key": "OPENAI_API_KEY",
    },
    "ollama": {
        "module": "langchain_ollama",
        "class": "ChatOllama",
        "env_key": None,  # Ollama runs locally, no API key needed
    },
}


class LLMClient:
    """Wrapper around a LangChain chat model with lazy initialization."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._model = None  # Lazy init

    @property
    def available(self) -> bool:
        """Check if the LLM provider is usable (installed + API key present)."""
        if not self._config.enabled:
            return False

        info = _PROVIDER_MAP.get(self._config.provider)
        if not info:
            return False

        # Check if the provider package is installed
        try:
            __import__(info["module"])
        except ImportError:
            return False

        # Check API key (Ollama doesn't need one)
        if info["env_key"] and not os.environ.get(info["env_key"]):
            return False

        return True

    def _get_model(self):
        """Lazily initialize the LangChain chat model."""
        if self._model is not None:
            return self._model

        info = _PROVIDER_MAP.get(self._config.provider)
        if not info:
            raise ValueError(f"Unknown LLM provider: {self._config.provider}")

        try:
            module = __import__(info["module"], fromlist=[info["class"]])
            model_class = getattr(module, info["class"])
        except ImportError:
            raise RuntimeError(
                f"LLM provider '{self._config.provider}' requires package "
                f"'{info['module']}'. Install with: pip install {info['module']}"
            )

        kwargs = {
            "model": self._config.model,
            "temperature": self._config.temperature,
        }
        if self._config.base_url:
            kwargs["base_url"] = self._config.base_url

        self._model = model_class(**kwargs)
        return self._model

    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke the LLM with a text prompt and return the response as a string."""
        model = self._get_model()
        response = model.invoke(prompt, **kwargs)
        return response.content

    def invoke_structured(
        self, prompt: str, output_schema: type[BaseModel], **kwargs
    ) -> BaseModel:
        """Invoke the LLM and parse the response into a Pydantic model."""
        model = self._get_model()
        structured = model.with_structured_output(output_schema)
        return structured.invoke(prompt, **kwargs)


def get_llm_client(config: LLMConfig) -> LLMClient:
    """Factory to create an LLM client from config."""
    return LLMClient(config)
