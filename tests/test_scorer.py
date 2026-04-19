"""Tests for job-profile scoring."""

import pytest

from tycho.config import LocationConfig, ScoringConfig, ScoringWeights
from tycho.matcher.scorer import (
    _keyword_match_score,
    _location_match_score,
    _skills_overlap_score,
    _title_match_score,
    score_job,
    score_jobs,
)


class TestKeywordMatchScore:
    def test_full_match_full_confidence(self, sample_profile):
        # 8 keywords → confidence = 1.0, all match → score = 1.0
        keywords = ["python", "pytorch", "sql", "langchain", "onnx", "cuda", "react", "docker"]
        score = _keyword_match_score(keywords, sample_profile)
        assert score == pytest.approx(1.0)

    def test_full_match_low_confidence(self, sample_profile):
        # 3/3 keywords match but only 3 extracted → confidence = 3/8 = 0.375
        keywords = ["python", "pytorch", "sql"]
        score = _keyword_match_score(keywords, sample_profile)
        assert score == pytest.approx(0.375)

    def test_no_match(self, sample_profile):
        keywords = ["ruby", "elixir", "haskell", "erlang", "clojure", "ocaml", "prolog", "cobol"]
        score = _keyword_match_score(keywords, sample_profile)
        assert score == 0.0

    def test_partial_match(self, sample_profile):
        keywords = ["python", "ruby", "erlang", "clojure", "ocaml", "prolog", "cobol", "haskell"]
        score = _keyword_match_score(keywords, sample_profile)
        assert 0.0 < score < 1.0

    def test_empty_keywords(self, sample_profile):
        score = _keyword_match_score([], sample_profile)
        assert score == 0.0

    def test_matches_skill_tags(self, sample_profile):
        # "ml" is a tag on PyTorch, not a skill name — use 8 keywords for full confidence
        keywords = ["ml", "ai", "cv", "llm", "rag", "optimization", "cloud", "devops"]
        score = _keyword_match_score(keywords, sample_profile)
        assert score > 0.0

    def test_confidence_scales_linearly(self, sample_profile):
        # With 4 matching keywords out of 8 threshold, confidence = 0.5, match ratio = 1.0
        # → final score = 0.5
        keywords = ["python", "pytorch", "sql", "langchain"]
        score = _keyword_match_score(keywords, sample_profile, min_confidence_count=8)
        assert score == pytest.approx(0.5)

    def test_confidence_capped_at_one(self, sample_profile):
        # More keywords than threshold → confidence stays at 1.0
        keywords = ["python", "pytorch", "sql", "langchain", "onnx", "cuda", "react", "docker",
                    "ruby", "elixir"]
        score = _keyword_match_score(keywords, sample_profile, min_confidence_count=8)
        # 8 of 10 match (ruby, elixir don't) → 0.8 * 1.0 = 0.8
        assert score == pytest.approx(0.8)


class TestTitleMatchScore:
    def test_exact_title_match(self, sample_profile):
        score = _title_match_score("AI Engineer", sample_profile)
        assert score > 0.5

    def test_partial_title_match(self, sample_profile):
        score = _title_match_score("Senior AI Engineer", sample_profile)
        assert score > 0.0

    def test_no_match(self, sample_profile):
        score = _title_match_score("Chef", sample_profile)
        assert score == 0.0

    def test_empty_title(self, sample_profile):
        score = _title_match_score("", sample_profile)
        assert score == 0.0

    def test_experience_title_match(self, sample_profile):
        # "Technical Business Analyst" is an experience title
        score = _title_match_score("Business Analyst", sample_profile)
        assert score > 0.0


class TestSkillsOverlapScore:
    def test_full_overlap(self, sample_profile):
        # All 8 profile skills present → recall = 8/8 = 1.0
        keywords = ["python", "pytorch", "sql", "langchain", "onnx", "cuda", "react", "docker"]
        score = _skills_overlap_score(keywords, sample_profile)
        assert score == pytest.approx(1.0)

    def test_partial_overlap(self, sample_profile):
        # 4 of 8 profile skills present → recall = 4/8 = 0.5
        keywords = ["python", "pytorch", "sql", "langchain", "ruby", "elixir", "haskell", "cobol"]
        score = _skills_overlap_score(keywords, sample_profile)
        assert score == pytest.approx(0.5)

    def test_no_overlap(self, sample_profile):
        keywords = ["ruby", "elixir"]
        score = _skills_overlap_score(keywords, sample_profile)
        assert score == 0.0

    def test_not_penalised_by_extra_job_keywords(self, sample_profile):
        # Job listing 4 matching + 20 irrelevant skills should score same as 4 matching alone
        few = ["python", "pytorch", "sql", "langchain"]
        many = few + ["cobol", "fortran", "perl", "pascal", "haskell",
                      "erlang", "prolog", "assembly", "basic", "tcl",
                      "ada", "lisp", "scheme", "forth", "sml",
                      "ocaml", "idris", "agda", "lean", "coq"]
        assert _skills_overlap_score(few, sample_profile) == pytest.approx(
            _skills_overlap_score(many, sample_profile)
        )

    def test_empty_keywords(self, sample_profile):
        score = _skills_overlap_score([], sample_profile)
        assert score == 0.0

    def test_empty_profile(self):
        from tycho.models import Profile, PersonalInfo, SkillsData
        empty_profile = Profile(
            personal=PersonalInfo(name="Test", email="t@t.com"),
            skills=SkillsData(),
        )
        score = _skills_overlap_score(["python", "pytorch"], empty_profile)
        assert score == 0.0


class TestLocationMatchScore:
    def test_remote_english(self, scoring_config):
        assert _location_match_score("Remote", scoring_config) == 1.0

    def test_remote_spanish(self, scoring_config):
        assert _location_match_score("En remoto", scoring_config) == 1.0

    def test_madrid(self, scoring_config):
        assert _location_match_score("Madrid, Spain", scoring_config) == 1.0

    def test_london(self, scoring_config):
        assert _location_match_score("London, UK", scoring_config) == 1.0

    def test_edinburgh(self, scoring_config):
        assert _location_match_score("Edinburgh", scoring_config) == 1.0

    def test_unknown_location(self, scoring_config):
        assert _location_match_score("Tokyo, Japan", scoring_config) == 0.0

    def test_empty_location(self, scoring_config):
        assert _location_match_score("", scoring_config) == 0.5

    def test_spanish_locations(self, scoring_config):
        assert _location_match_score("Madrid, España", scoring_config) == 1.0
        assert _location_match_score("Edimburgo", scoring_config) == 1.0
        assert _location_match_score("Londres, Reino Unido", scoring_config) == 1.0

    def test_abbreviation_expansion(self):
        config = ScoringConfig(locations=LocationConfig(
            abbreviations={"md": "madrid", "es": "spain"},
        ))
        assert _location_match_score("MD", config) == 1.0
        assert _location_match_score("ES", config) == 1.0

    def test_word_boundary_no_false_positive(self, scoring_config):
        # "en" should NOT match inside "Senior Engineer"
        assert _location_match_score("Senior Engineer", scoring_config) == 0.0
        # "es" should NOT match inside "processes" or "addresses"
        assert _location_match_score("processes", scoring_config) == 0.0
        assert _location_match_score("addresses", scoring_config) == 0.0

    def test_abbreviation_word_boundary(self):
        config = ScoringConfig(locations=LocationConfig(
            abbreviations={"es": "spain"},
        ))
        # Standalone "ES" matches
        assert _location_match_score("ES", config) == 1.0
        # "es" inside a word does NOT match
        assert _location_match_score("processes", config) == 0.0

    def test_custom_config_locations(self):
        config = ScoringConfig(locations=LocationConfig(
            preferred=["berlin", "munich"],
            preferred_es=["berlín", "múnich"],
            remote_keywords=["remote", "teletrabajo"],
        ))
        assert _location_match_score("Berlin, Germany", config) == 1.0
        assert _location_match_score("Berlín", config) == 1.0
        assert _location_match_score("Teletrabajo", config) == 1.0
        # Default locations no longer match with custom config
        assert _location_match_score("Madrid, Spain", config) == 0.0


class TestScoreJob:
    def test_ml_job_scores_well(self, ml_job, sample_profile, scoring_config):
        score, details = score_job(ml_job, sample_profile, scoring_config)
        assert score > 0.3
        assert "keyword_match" in details
        assert "keyword_confidence" in details
        assert "title_match" in details
        assert "skills_overlap" in details
        assert "location_match" in details
        assert "job_keywords" in details
        assert "total" in details
        assert details["total"] == score

    def test_backend_job_scores(self, backend_job, sample_profile, scoring_config):
        score, details = score_job(backend_job, sample_profile, scoring_config)
        assert score > 0.0
        assert details["location_match"] == 1.0  # London

    def test_empty_job(self, empty_job, sample_profile, scoring_config):
        score, details = score_job(empty_job, sample_profile, scoring_config)
        assert score >= 0.0
        assert details["keyword_match"] == 0.0
        assert details["title_match"] == 0.0

    def test_scores_are_rounded(self, ml_job, sample_profile, scoring_config):
        score, details = score_job(ml_job, sample_profile, scoring_config)
        # Check rounded to 3 decimals
        assert score == round(score, 3)
        for key in ["keyword_match", "title_match", "skills_overlap", "location_match"]:
            assert details[key] == round(details[key], 3)

    def test_custom_weights(self, ml_job, sample_profile):
        config = ScoringConfig(weights=ScoringWeights(
            keyword_match=1.0, title_match=0.0, skills_overlap=0.0, location_match=0.0
        ))
        score, details = score_job(ml_job, sample_profile, config)
        # Score should equal keyword_match since weight is 1.0
        assert score == pytest.approx(details["keyword_match"], abs=0.001)


class TestScoreJobs:
    def test_scores_all_jobs(self, ml_job, backend_job, sample_profile, scoring_config):
        jobs = [ml_job, backend_job]
        result = score_jobs(jobs, sample_profile, scoring_config)
        assert len(result) == 2
        assert all(j.score is not None for j in result)
        assert all(j.score_details is not None for j in result)

    def test_modifies_in_place(self, ml_job, sample_profile, scoring_config):
        original_id = id(ml_job)
        result = score_jobs([ml_job], sample_profile, scoring_config)
        assert id(result[0]) == original_id
        assert ml_job.score is not None
