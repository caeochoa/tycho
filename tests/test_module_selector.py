"""Tests for module selection and tailoring."""

from unittest.mock import MagicMock

import pytest

from tycho.cv.module_selector import (
    _get_bullet_text,
    _llm_rewrite_bullets,
    _llm_rewrite_summary,
    _score_bullet,
    _select_skills,
    _select_summary,
    select_modules,
)
from tycho.models import Bullet
from tycho.cv.module_selector import RewrittenBullets, RewrittenSummary


class TestSelectSummary:
    def test_returns_summary_string(self, sample_profile):
        summary = _select_summary(sample_profile)
        assert isinstance(summary, str)
        assert summary != ""

    def test_returns_plain_summary(self, sample_profile):
        summary = _select_summary(sample_profile)
        assert summary == sample_profile.personal.summary


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
        bullet = Bullet(text="Test", tags=["python", "ml", "ai"], priority=1)
        score = _score_bullet(bullet, {"python", "ml"})
        assert score > 0.0

    def test_no_matching_tags(self):
        bullet = Bullet(text="Test", tags=["web", "frontend"], priority=1)
        score = _score_bullet(bullet, {"python", "ml"})
        assert score > 0.0  # Still gets priority bonus

    def test_no_tags(self):
        bullet = Bullet(text="Test", tags=[], priority=1)
        score = _score_bullet(bullet, {"python"})
        assert score == 0.0

    def test_priority_affects_score(self):
        b1 = Bullet(text="Test", tags=["python"], priority=1)
        b3 = Bullet(text="Test", tags=["python"], priority=3)
        score1 = _score_bullet(b1, {"python"})
        score3 = _score_bullet(b3, {"python"})
        assert score1 > score3


class TestGetBulletText:
    def test_default_text(self):
        bullet = Bullet(text="Default text")
        assert _get_bullet_text(bullet, "en") == "Default text"

    def test_spanish_text(self):
        bullet = Bullet(text="Default", text_es="Texto en español")
        assert _get_bullet_text(bullet, "es") == "Texto en español"

    def test_empty_spanish_falls_to_default(self):
        bullet = Bullet(text="Default", text_es="")
        assert _get_bullet_text(bullet, "es") == "Default"


class TestSelectModules:
    def test_returns_tailored_profile(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job)
        assert tailored.job_id == ml_job.id
        assert tailored.personal.name == "Cesar Ochoa"
        assert len(tailored.experience) > 0
        assert len(tailored.education) > 0
        assert len(tailored.skills) > 0

    def test_ml_job_gets_summary(self, sample_profile, ml_job):
        tailored = select_modules(sample_profile, ml_job)
        assert isinstance(tailored.summary, str)
        assert tailored.summary != ""

    def test_backend_job_gets_summary(self, sample_profile, backend_job):
        tailored = select_modules(sample_profile, backend_job)
        assert isinstance(tailored.summary, str)
        assert tailored.summary != ""

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

    def test_focus_field_is_none(self, sample_profile, ml_job):
        """focus is always None — focus detection removed."""
        tailored = select_modules(sample_profile, ml_job)
        assert tailored.focus is None

    def test_no_llm_client_phase1_behavior(self, sample_profile, ml_job):
        """No LLM client should produce same results as Phase 1."""
        tailored = select_modules(sample_profile, ml_job, llm_client=None)
        assert tailored.job_id == ml_job.id
        assert len(tailored.experience) > 0


class TestLLMRewriteBullets:
    def test_rewrite_called_and_replaces_text(self, mock_llm_client):
        mock_llm_client.invoke_structured.return_value = RewrittenBullets(
            bullets=["Rewritten bullet A", "Rewritten bullet B"]
        )
        originals = ["Original bullet A", "Original bullet B"]
        result = _llm_rewrite_bullets(
            mock_llm_client, originals, "ML Engineer", "DeepTech", "Python, PyTorch"
        )
        assert result == ["Rewritten bullet A", "Rewritten bullet B"]
        mock_llm_client.invoke_structured.assert_called_once()

    def test_wrong_count_falls_back(self, mock_llm_client):
        mock_llm_client.invoke_structured.return_value = RewrittenBullets(
            bullets=["Only one bullet"]
        )
        originals = ["Bullet 1", "Bullet 2"]
        result = _llm_rewrite_bullets(
            mock_llm_client, originals, "Title", "Co", "desc"
        )
        assert result == originals  # fallback

    def test_empty_bullets_returns_empty(self, mock_llm_client):
        result = _llm_rewrite_bullets(mock_llm_client, [], "Title", "Co", "desc")
        assert result == []
        mock_llm_client.invoke_structured.assert_not_called()

    def test_exception_propagates(self, mock_llm_client):
        """_llm_rewrite_bullets itself propagates — caller wraps in try/except."""
        mock_llm_client.invoke_structured.side_effect = RuntimeError("API error")
        with pytest.raises(RuntimeError):
            _llm_rewrite_bullets(mock_llm_client, ["bullet"], "Title", "Co", "desc")


class TestLLMRewriteSummary:
    def test_rewrite_returns_new_summary(self, mock_llm_client):
        mock_llm_client.invoke_structured.return_value = RewrittenSummary(
            summary="Tailored summary text."
        )
        result = _llm_rewrite_summary(
            mock_llm_client, "Original summary.", "ML Engineer", "DeepTech", "desc"
        )
        assert result == "Tailored summary text."

    def test_empty_summary_returns_empty(self, mock_llm_client):
        result = _llm_rewrite_summary(mock_llm_client, "", "Title", "Co", "desc")
        assert result == ""
        mock_llm_client.invoke_structured.assert_not_called()

    def test_exception_propagates(self, mock_llm_client):
        mock_llm_client.invoke_structured.side_effect = RuntimeError("API error")
        with pytest.raises(RuntimeError):
            _llm_rewrite_summary(mock_llm_client, "Summary", "Title", "Co", "desc")


class TestSelectModulesWithLLM:
    def test_select_modules_with_llm_rewrites(self, sample_profile, ml_job, mock_llm_client):
        """LLM client integration: rewrites are applied through select_modules."""
        mock_llm_client.invoke_structured.return_value = RewrittenBullets(
            bullets=["Rewritten bullet"]
        )
        # Override for summary call (first invoke_structured call)
        rewritten_summary = RewrittenSummary(summary="Tailored summary.")
        rewritten_bullets_single = RewrittenBullets(bullets=["Rewritten bullet"])
        rewritten_bullets_double = RewrittenBullets(bullets=["Rewritten bullet A", "Rewritten bullet B"])

        def structured_side_effect(prompt, schema):
            if schema is RewrittenSummary:
                return rewritten_summary
            elif schema is RewrittenBullets:
                # Return correct number of bullets based on prompt content
                if "\n2. " in prompt:
                    return rewritten_bullets_double
                return rewritten_bullets_single
            # LLMKeywordResult for keyword extraction
            from tycho.models import LLMKeywordResult
            return LLMKeywordResult(
                keywords=["python", "pytorch"],
                required_skills=["python"],
                nice_to_have_skills=[],
            )

        mock_llm_client.invoke_structured.side_effect = structured_side_effect

        tailored = select_modules(sample_profile, ml_job, llm_client=mock_llm_client)
        assert tailored.job_id == ml_job.id
        assert len(tailored.experience) > 0

    def test_select_modules_llm_failure_graceful(self, sample_profile, ml_job, mock_llm_client):
        """LLM failures should not break select_modules."""
        from tycho.models import LLMKeywordResult

        def structured_side_effect(prompt, schema):
            if schema is RewrittenSummary or schema is RewrittenBullets:
                raise RuntimeError("API error")
            return LLMKeywordResult(
                keywords=["python"],
                required_skills=["python"],
                nice_to_have_skills=[],
            )

        mock_llm_client.invoke_structured.side_effect = structured_side_effect

        # Should still work, falling back to original text
        tailored = select_modules(sample_profile, ml_job, llm_client=mock_llm_client)
        assert tailored.job_id == ml_job.id
        assert len(tailored.experience) > 0
