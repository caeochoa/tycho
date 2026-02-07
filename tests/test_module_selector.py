"""Tests for module selection and tailoring."""

import pytest

from tycho.cv.module_selector import (
    _detect_focus,
    _get_bullet_text,
    _score_bullet,
    _select_skills,
    _select_summary,
    select_modules,
)
from tycho.models import Bullet, BulletVariations


class TestDetectFocus:
    def test_ml_focus(self):
        keywords = {"pytorch", "tensorflow", "deep learning", "cuda"}
        focus = _detect_focus(keywords, "ML Engineer")
        assert focus == "ml_focus"

    def test_backend_focus(self):
        keywords = {"docker", "kubernetes", "fastapi", "microservices"}
        focus = _detect_focus(keywords, "Backend Engineer")
        assert focus == "backend_focus"

    def test_data_focus(self):
        keywords = {"pandas", "statistics", "analytics"}
        focus = _detect_focus(keywords, "Data Scientist")
        assert focus == "data_focus"

    def test_title_gives_bonus(self):
        # "machine learning" in title should boost ml_focus
        keywords = {"python"}  # neutral keyword
        focus = _detect_focus(keywords, "Machine Learning Engineer")
        assert focus == "ml_focus"

    def test_no_focus(self):
        keywords = {"communication", "teamwork"}
        focus = _detect_focus(keywords, "Manager")
        assert focus is None

    def test_empty_keywords(self):
        focus = _detect_focus(set(), "Generic Role")
        assert focus is None


class TestSelectSummary:
    def test_ml_focus_variation(self, sample_profile):
        summary = _select_summary(sample_profile, "ml_focus", "en")
        assert "ML Engineer" in summary or "PyTorch" in summary

    def test_backend_focus_variation(self, sample_profile):
        summary = _select_summary(sample_profile, "backend_focus", "en")
        assert "Software Engineer" in summary or "backend" in summary.lower()

    def test_no_focus_uses_default(self, sample_profile):
        summary = _select_summary(sample_profile, None, "en")
        assert summary == sample_profile.personal.summary.default

    def test_unknown_focus_uses_default(self, sample_profile):
        summary = _select_summary(sample_profile, "nonexistent_focus", "en")
        assert summary == sample_profile.personal.summary.default


class TestSelectSkills:
    def test_relevant_skills_ranked_higher(self, sample_profile):
        job_keywords = {"python", "pytorch", "langchain"}
        skills = _select_skills(sample_profile, job_keywords)
        # Python, PyTorch, LangChain should be near the top
        top_5 = skills[:5]
        assert "Python" in top_5
        assert "PyTorch" in top_5
        assert "LangChain" in top_5

    def test_max_15_skills(self, sample_profile):
        skills = _select_skills(sample_profile, {"python", "pytorch"})
        assert len(skills) <= 15

    def test_empty_keywords(self, sample_profile):
        skills = _select_skills(sample_profile, set())
        assert len(skills) > 0  # Still returns skills ranked by priority


class TestScoreBullet:
    def test_matching_tags(self):
        bullet = Bullet(id="b1", text="Test", tags=["python", "ml", "ai"], priority=1)
        score = _score_bullet(bullet, {"python", "ml"})
        assert score > 0.0

    def test_no_matching_tags(self):
        bullet = Bullet(id="b1", text="Test", tags=["web", "frontend"], priority=1)
        score = _score_bullet(bullet, {"python", "ml"})
        assert score > 0.0  # Still gets priority bonus

    def test_no_tags(self):
        bullet = Bullet(id="b1", text="Test", tags=[], priority=1)
        score = _score_bullet(bullet, {"python"})
        assert score == 0.0

    def test_priority_affects_score(self):
        b1 = Bullet(id="b1", text="Test", tags=["python"], priority=1)
        b3 = Bullet(id="b3", text="Test", tags=["python"], priority=3)
        score1 = _score_bullet(b1, {"python"})
        score3 = _score_bullet(b3, {"python"})
        assert score1 > score3


class TestGetBulletText:
    def test_default_text(self):
        bullet = Bullet(id="b1", text="Default text")
        assert _get_bullet_text(bullet, None, "en") == "Default text"

    def test_ml_focus_variation(self):
        bullet = Bullet(
            id="b1",
            text="Default text",
            variations=BulletVariations(ml_focus="ML version"),
        )
        assert _get_bullet_text(bullet, "ml_focus", "en") == "ML version"

    def test_spanish_text(self):
        bullet = Bullet(id="b1", text="Default", text_es="Texto en español")
        assert _get_bullet_text(bullet, None, "es") == "Texto en español"

    def test_spanish_takes_priority_over_variation(self):
        bullet = Bullet(
            id="b1",
            text="Default",
            text_es="Spanish text",
            variations=BulletVariations(ml_focus="ML version"),
        )
        # Spanish should take priority when language is "es"
        assert _get_bullet_text(bullet, "ml_focus", "es") == "Spanish text"

    def test_empty_spanish_falls_to_variation(self):
        bullet = Bullet(
            id="b1",
            text="Default",
            text_es="",
            variations=BulletVariations(ml_focus="ML version"),
        )
        assert _get_bullet_text(bullet, "ml_focus", "es") == "ML version"

    def test_no_variation_falls_to_default(self):
        bullet = Bullet(id="b1", text="Default", variations=BulletVariations())
        assert _get_bullet_text(bullet, "ml_focus", "en") == "Default"


class TestSelectModules:
    def test_returns_tailored_profile(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job)
        assert tailored.job_id == ml_job.id
        assert tailored.personal.name == "Cesar Ochoa"
        assert len(tailored.experience) > 0
        assert len(tailored.education) > 0
        assert len(tailored.skills) > 0

    def test_ml_job_gets_ml_summary(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job)
        # Should pick ml_focus variation
        assert "ML" in tailored.summary or "PyTorch" in tailored.summary

    def test_backend_job_gets_backend_summary(self, sample_profile, backend_job):
        tailored = select_modules(sample_profile, backend_job)
        assert "backend" in tailored.summary.lower() or "Software" in tailored.summary

    def test_spanish_language(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job, language="es")
        # Experience entries should use Spanish titles
        oesia = next(e for e in tailored.experience if e.id == "oesia_ai_engineer")
        assert oesia.title == "Ingeniero de IA"

    def test_max_bullets_respected(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job, max_bullets_per_entry=1)
        for entry in tailored.experience:
            assert len(entry.bullets) <= 1

    def test_languages_included(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job)
        assert len(tailored.languages) == 2

    def test_disabled_entries_excluded(self, sample_profile, ml_job):
        # Disable an experience entry
        sample_profile.experience[1].enabled = False
        tailored = select_modules(sample_profile, ml_job)
        ids = [e.id for e in tailored.experience]
        assert "acturis_analyst" not in ids

    def test_bullets_have_relevance_scores(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job)
        for entry in tailored.experience:
            for bullet in entry.bullets:
                assert isinstance(bullet.relevance_score, float)
