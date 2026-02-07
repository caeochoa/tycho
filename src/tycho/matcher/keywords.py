"""Keyword extraction from job descriptions.

Phase 1: Simple regex/pattern matching against known skill lists.
Phase 2: LLM-based extraction with regex fallback.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from tycho.models import LLMKeywordResult, Profile

logger = logging.getLogger(__name__)

# Common tech keywords to look for (beyond profile skills)
TECH_KEYWORDS = {
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "ruby", "php", "swift", "kotlin", "scala", "r", "matlab",
    "pytorch", "tensorflow", "keras", "scikit-learn", "sklearn",
    "pandas", "numpy", "scipy", "matplotlib",
    "langchain", "llm", "rag", "gpt", "bert", "transformer",
    "docker", "kubernetes", "aws", "azure", "gcp", "cloud",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "react", "vue", "angular", "node", "fastapi", "flask", "django",
    "git", "ci/cd", "linux", "agile", "scrum",
    "machine learning", "deep learning", "computer vision", "nlp",
    "natural language processing", "reinforcement learning",
    "data science", "data engineering", "mlops",
    "onnx", "cuda", "tensorrt",
    "api", "rest", "graphql", "microservices",
}


def extract_keywords(
    description: str,
    profile: Profile | None = None,
    llm_client=None,
) -> list[str]:
    """Extract relevant keywords from a job description.

    If llm_client is available, merges LLM results with regex results.
    Falls back to regex-only if LLM is unavailable or fails.
    """
    regex_keywords = _extract_keywords_regex(description, profile)

    if llm_client is not None and getattr(llm_client, "available", False):
        try:
            llm_result = extract_keywords_llm(description, llm_client)
            # Merge LLM keywords with regex keywords
            merged = set(regex_keywords)
            for kw in llm_result.keywords:
                merged.add(kw.lower())
            for kw in llm_result.required_skills:
                merged.add(kw.lower())
            for kw in llm_result.nice_to_have_skills:
                merged.add(kw.lower())
            return sorted(merged)
        except Exception:
            logger.debug("LLM keyword extraction failed, using regex fallback", exc_info=True)

    return regex_keywords


def _extract_keywords_regex(description: str, profile: Profile | None = None) -> list[str]:
    """Extract relevant keywords using regex pattern matching (Phase 1 behavior)."""
    text = description.lower()
    found = []

    # Check against known tech keywords
    for kw in TECH_KEYWORDS:
        if _word_match(kw, text):
            found.append(kw)

    # Check against profile skills if available
    if profile:
        for skill in profile.skills.technical:
            name_lower = skill.name.lower()
            if name_lower not in found and _word_match(name_lower, text):
                found.append(name_lower)

    return sorted(set(found))


def extract_keywords_llm(description: str, llm_client) -> LLMKeywordResult:
    """Extract keywords from a job description using an LLM.

    Returns an LLMKeywordResult with structured keyword data.
    """
    prompt = (
        "Extract technical keywords, required skills, and nice-to-have skills "
        "from the following job description. Also determine the primary focus area "
        "as one of: 'ml_focus', 'backend_focus', 'data_focus', or null if unclear.\n\n"
        f"Job description:\n{description[:3000]}"
    )
    return llm_client.invoke_structured(prompt, LLMKeywordResult)


def _word_match(keyword: str, text: str) -> bool:
    """Check if keyword appears as a word/phrase in text."""
    text_lower = text.lower()
    kw_lower = keyword.lower()
    # For multi-word phrases or keywords with non-alphanumeric chars (c++, c#, ci/cd)
    if " " in keyword or not keyword.isalnum():
        return kw_lower in text_lower
    # For single alphanumeric words, use word boundary matching
    pattern = rf"\b{re.escape(kw_lower)}\b"
    return bool(re.search(pattern, text_lower))
