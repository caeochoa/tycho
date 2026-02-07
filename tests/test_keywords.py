"""Tests for keyword extraction."""

from unittest.mock import MagicMock

from tycho.matcher.keywords import (
    _extract_keywords_regex,
    _word_match,
    extract_keywords,
    extract_keywords_llm,
)
from tycho.models import LLMKeywordResult


class TestWordMatch:
    def test_single_word(self):
        assert _word_match("python", "We use Python for ML") is True

    def test_single_word_case_insensitive(self):
        assert _word_match("python", "PYTHON is great") is True

    def test_single_word_no_partial(self):
        # "sql" should not match "postgresql" as a word boundary match
        assert _word_match("sql", "We use PostgreSQL") is False

    def test_single_word_boundaries(self):
        assert _word_match("sql", "Experience with SQL required") is True

    def test_multi_word_phrase(self):
        assert _word_match("machine learning", "Experience in machine learning required") is True

    def test_multi_word_phrase_not_found(self):
        assert _word_match("machine learning", "We need a machine and some learning") is False

    def test_empty_text(self):
        assert _word_match("python", "") is False

    def test_regex_special_chars(self):
        # re.escape should handle "c++"
        assert _word_match("c++", "Experience with C++ required") is True


class TestExtractKeywords:
    def test_basic_extraction(self):
        desc = "We need a Python developer with PyTorch and SQL experience."
        keywords = extract_keywords(desc)
        assert "python" in keywords
        assert "pytorch" in keywords
        assert "sql" in keywords

    def test_empty_description(self):
        assert extract_keywords("") == []

    def test_no_keywords(self):
        assert extract_keywords("Looking for a friendly team player") == []

    def test_multi_word_keywords(self):
        desc = "Must have machine learning and deep learning experience."
        keywords = extract_keywords(desc)
        assert "machine learning" in keywords
        assert "deep learning" in keywords

    def test_sorted_output(self):
        desc = "Python, PyTorch, SQL, Azure, Docker, CUDA"
        keywords = extract_keywords(desc)
        assert keywords == sorted(keywords)

    def test_deduplicated(self):
        desc = "Python Python Python PyTorch PyTorch"
        keywords = extract_keywords(desc)
        assert keywords.count("python") == 1
        assert keywords.count("pytorch") == 1

    def test_with_profile_skills(self, sample_profile):
        desc = "We need React and LangChain experience."
        keywords = extract_keywords(desc, sample_profile)
        assert "react" in keywords
        assert "langchain" in keywords

    def test_profile_skills_not_duplicated(self, sample_profile):
        desc = "Python and PyTorch required."
        keywords = extract_keywords(desc, sample_profile)
        assert keywords.count("python") == 1


class TestExtractKeywordsWithLLM:
    def test_llm_merges_with_regex(self, sample_profile, mock_llm_client):
        """LLM keywords should be merged with regex keywords."""
        mock_llm_client.invoke_structured.return_value = LLMKeywordResult(
            keywords=["custom-framework"],
            required_skills=["advanced-ml"],
            nice_to_have_skills=[],
        )

        desc = "We need Python and PyTorch experience."
        keywords = extract_keywords(desc, sample_profile, llm_client=mock_llm_client)

        # Regex keywords should still be present
        assert "python" in keywords
        assert "pytorch" in keywords
        # LLM keywords should be merged in
        assert "custom-framework" in keywords
        assert "advanced-ml" in keywords

    def test_llm_failure_falls_back_to_regex(self, sample_profile, mock_llm_client):
        """If LLM fails, should silently fall back to regex results."""
        mock_llm_client.invoke_structured.side_effect = RuntimeError("API error")

        desc = "Python and Docker experience."
        keywords = extract_keywords(desc, sample_profile, llm_client=mock_llm_client)

        # Should still get regex results
        assert "python" in keywords
        assert "docker" in keywords

    def test_none_client_uses_regex(self):
        """No client should produce identical results to regex-only."""
        desc = "Python, PyTorch, SQL required."
        kw_none = extract_keywords(desc, llm_client=None)
        kw_regex = _extract_keywords_regex(desc)
        assert kw_none == kw_regex

    def test_unavailable_client_uses_regex(self):
        """Client with available=False should produce regex-only results."""
        client = MagicMock()
        client.available = False

        desc = "Python and Docker experience."
        kw_with = extract_keywords(desc, llm_client=client)
        kw_regex = _extract_keywords_regex(desc)
        assert kw_with == kw_regex
        # invoke_structured should never be called
        client.invoke_structured.assert_not_called()
