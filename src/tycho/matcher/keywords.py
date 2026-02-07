"""Keyword extraction from job descriptions.

Phase 1: Simple regex/pattern matching against known skill lists.
Phase 2: LLM-based extraction.
"""

import re
from collections import Counter

from tycho.models import Profile


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


def extract_keywords(description: str, profile: Profile | None = None) -> list[str]:
    """Extract relevant keywords from a job description."""
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
