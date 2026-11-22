"""Tests that the real profile lists AI-native skills matching keywords.py's TECH_KEYWORDS.

Without these, AI-lab postings that describe work as prompts/agents/evals rather
than naming frameworks score 0 on skills_overlap even after keyword extraction
picks the terms up.
"""

import os

from tycho.cv.profile_loader import load_profile
from tycho.matcher.scorer import _keyword_match_score, _skills_overlap_score

REAL_PROFILE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "profile")
)


def _real_profile():
    return load_profile(REAL_PROFILE_DIR)


AI_TERMS = ["ai agents", "prompt engineering", "evals", "fine-tuning"]


class TestAINativeSkillsInProfile:
    def test_ai_native_terms_are_profile_skills(self):
        names = {s.name.lower() for s in _real_profile().skills.technical}
        for term in AI_TERMS + ["model deployment"]:
            assert term in names, f"{term!r} missing from profile/skills.yaml"

    def test_no_duplicate_skills(self):
        names = [s.name.lower() for s in _real_profile().skills.technical]
        assert len(names) == len(set(names))

    def test_core_pool_stays_small(self):
        # Every priority-1 skill dilutes skills_overlap for all jobs.
        core = [s for s in _real_profile().skills.technical if s.priority == 1]
        assert len(core) <= 12

    def test_generic_terms_not_core(self):
        core = {s.name.lower() for s in _real_profile().skills.technical if s.priority == 1}
        assert not core & {"deployment", "evaluations", "agents"}

    def test_scores_credit_ai_native_terms(self):
        profile = _real_profile()
        assert _keyword_match_score(AI_TERMS, profile, min_confidence_count=4) > 0.0
        assert _skills_overlap_score(AI_TERMS, profile) > _skills_overlap_score(["python"], profile)
