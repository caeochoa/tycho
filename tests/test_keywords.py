"""Tests for keyword extraction."""

from tycho.matcher.keywords import _word_match, extract_keywords


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
