"""Tests that the real profile lists AI-native skills matching keywords.py's TECH_KEYWORDS.

Without these, AI-lab postings that describe work as prompts/agents/evals rather
than naming frameworks score 0 on skills_overlap even after keyword extraction
picks the terms up (see OpenAI job li-4417173113).
"""

import os

from tycho.cv.profile_loader import load_profile
from tycho.matcher.scorer import _keyword_match_score, _skills_overlap_score

REAL_PROFILE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "profile")
)


def _real_profile():
    return load_profile(REAL_PROFILE_DIR)


class TestAINativeSkillsInProfile:
    def test_ai_native_terms_are_profile_skills(self):
        profile = _real_profile()
        skill_names = {s.name.lower() for s in profile.skills.technical}
        for term in ["agents", "prompt engineering", "evals", "evaluations", "fine-tuning", "deployment"]:
            assert term in skill_names, f"{term!r} missing from profile/skills.yaml"

    def test_keyword_match_score_credits_ai_native_terms(self):
        profile = _real_profile()
        job_keywords = ["agents", "deployment", "evals", "evaluations"]
        score = _keyword_match_score(job_keywords, profile, min_confidence_count=8)
        assert score > 0.0

    def test_ai_native_terms_are_priority_1(self):
        # skills_overlap only counts priority-1 skills as the core pool (scorer.py:133);
        # these need to be priority 1 to actually move that component, not just keyword_match.
        profile = _real_profile()
        priorities = {s.name.lower(): s.priority for s in profile.skills.technical}
        for term in ["agents", "prompt engineering", "evals", "evaluations", "deployment"]:
            assert priorities[term] == 1, f"{term!r} is priority {priorities[term]}, expected 1"

    def test_skills_overlap_credits_ai_native_terms(self):
        profile = _real_profile()
        job_keywords = ["agents", "deployment", "evals", "evaluations"]
        score = _skills_overlap_score(job_keywords, profile)
        assert score > 0.0
