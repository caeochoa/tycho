"""Tests for profile loading from multi-file YAML."""

import pytest
import yaml

from tycho.cv.profile_loader import load_profile, validate_profile


class TestLoadProfile:
    def test_loads_all_sections(self, profile_dir):
        profile = load_profile(profile_dir)
        assert profile.personal.name == "Cesar Ochoa"
        assert len(profile.skills.technical) == 8
        assert len(profile.skills.languages) == 2
        assert len(profile.experience) == 2
        assert len(profile.education) == 1
        assert len(profile.other) == 1

    def test_experience_sorted_by_priority(self, profile_dir):
        profile = load_profile(profile_dir)
        priorities = [e.priority for e in profile.experience]
        assert priorities == sorted(priorities)

    def test_bullets_loaded(self, profile_dir):
        profile = load_profile(profile_dir)
        oesia = next(e for e in profile.experience if e.id == "oesia_ai_engineer")
        assert len(oesia.bullets) == 2
        assert oesia.bullets[0].id == "oesia_rag"

    def test_bullet_variations_loaded(self, profile_dir):
        profile = load_profile(profile_dir)
        oesia = next(e for e in profile.experience if e.id == "oesia_ai_engineer")
        rag_bullet = next(b for b in oesia.bullets if b.id == "oesia_rag")
        assert rag_bullet.variations.ml_focus is not None
        assert "LangChain" in rag_bullet.variations.ml_focus

    def test_summary_variations(self, profile_dir):
        profile = load_profile(profile_dir)
        assert profile.personal.summary.default != ""
        assert profile.personal.summary.variations.ml_focus is not None

    def test_spanish_fields(self, profile_dir):
        profile = load_profile(profile_dir)
        assert profile.personal.name_es == "César Ochoa Munárriz"
        oesia = next(e for e in profile.experience if e.id == "oesia_ai_engineer")
        assert oesia.title_es == "Ingeniero de IA"

    def test_disabled_entry_skipped(self, profile_dir):
        # Add a disabled entry
        disabled_data = {
            "id": "disabled_job",
            "type": "experience",
            "company": "Old Corp",
            "title": "Old Role",
            "dates": "2010",
            "priority": 10,
            "tags": [],
            "skills": [],
            "bullets": [],
            "enabled": False,
        }
        (profile_dir / "experience" / "disabled.yaml").write_text(yaml.dump(disabled_data))

        profile = load_profile(profile_dir)
        ids = [e.id for e in profile.experience]
        assert "disabled_job" not in ids

    def test_empty_other_dir(self, profile_dir):
        # Remove all files from other/
        for f in (profile_dir / "other").glob("*.yaml"):
            f.unlink()
        profile = load_profile(profile_dir)
        assert profile.other == []

    def test_education_gpa(self, profile_dir):
        profile = load_profile(profile_dir)
        edinburgh = next(e for e in profile.education if e.id == "edinburgh_msc")
        assert edinburgh.gpa == "3.7/4"


class TestValidateProfile:
    def test_valid_profile(self, profile_dir):
        errors = validate_profile(profile_dir)
        assert errors == []

    def test_missing_personal_yaml(self, profile_dir):
        (profile_dir / "personal.yaml").unlink()
        errors = validate_profile(profile_dir)
        assert any("personal.yaml" in e for e in errors)

    def test_missing_skills_yaml(self, profile_dir):
        (profile_dir / "skills.yaml").unlink()
        errors = validate_profile(profile_dir)
        assert any("skills.yaml" in e for e in errors)

    def test_missing_experience_dir(self, profile_dir):
        import shutil
        shutil.rmtree(profile_dir / "experience")
        errors = validate_profile(profile_dir)
        assert any("experience" in e for e in errors)

    def test_empty_experience_dir(self, profile_dir):
        for f in (profile_dir / "experience").glob("*.yaml"):
            f.unlink()
        errors = validate_profile(profile_dir)
        assert any("experience" in e for e in errors)

    def test_missing_education_dir(self, profile_dir):
        import shutil
        shutil.rmtree(profile_dir / "education")
        errors = validate_profile(profile_dir)
        assert any("education" in e for e in errors)

    def test_malformed_yaml(self, profile_dir):
        (profile_dir / "personal.yaml").write_text(": invalid: yaml: {{{}}")
        errors = validate_profile(profile_dir)
        assert len(errors) > 0
