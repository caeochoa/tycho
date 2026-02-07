"""Tests for Pydantic data models."""

from datetime import datetime

import pytest

from tycho.models import (
    Bullet,
    BulletVariations,
    EducationModule,
    ExperienceModule,
    Job,
    JobStatus,
    Language,
    OtherModule,
    PersonalInfo,
    Profile,
    Skill,
    SkillsData,
    Summary,
    SummaryVariations,
    TailoredBullet,
    TailoredEntry,
    TailoredProfile,
)


class TestJobStatus:
    def test_enum_values(self):
        assert JobStatus.NEW == "new"
        assert JobStatus.REVIEWED == "reviewed"
        assert JobStatus.INTERESTED == "interested"
        assert JobStatus.APPLIED == "applied"
        assert JobStatus.REJECTED == "rejected"
        assert JobStatus.ARCHIVED == "archived"

    def test_from_string(self):
        assert JobStatus("new") == JobStatus.NEW
        assert JobStatus("applied") == JobStatus.APPLIED

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            JobStatus("invalid")


class TestJob:
    def test_minimal_job(self):
        job = Job(id="1", source="indeed", title="Dev", company="Corp")
        assert job.id == "1"
        assert job.status == JobStatus.NEW
        assert job.tags == []
        assert job.score is None
        assert job.description == ""

    def test_full_job(self):
        job = Job(
            id="1",
            source="linkedin",
            source_id="ln_123",
            title="ML Engineer",
            company="AI Corp",
            location="Madrid",
            description="A great role",
            url="https://example.com",
            salary_min=50000.0,
            salary_max=80000.0,
            date_posted=datetime(2025, 1, 15),
            tags=["python", "ml"],
            score=0.85,
            score_details={"keyword_match": 0.9},
            status=JobStatus.INTERESTED,
            cv_path="/output/cv.pdf",
            notes="Looks good",
        )
        assert job.salary_min == 50000.0
        assert job.score == 0.85
        assert job.tags == ["python", "ml"]

    def test_default_date_collected(self):
        job = Job(id="1", source="test", title="Dev", company="Corp")
        assert isinstance(job.date_collected, datetime)

    def test_none_optionals(self):
        job = Job(id="1", source="test", title="Dev", company="Corp")
        assert job.salary_min is None
        assert job.salary_max is None
        assert job.date_posted is None
        assert job.score is None
        assert job.cv_path is None
        assert job.cover_letter_path is None
        assert job.notes is None


class TestBullet:
    def test_minimal_bullet(self):
        b = Bullet(id="b1", text="Did something.")
        assert b.text_es == ""
        assert b.tags == []
        assert b.priority == 1
        assert b.variations.ml_focus is None

    def test_bullet_with_variations(self):
        b = Bullet(
            id="b1",
            text="Did something.",
            variations=BulletVariations(ml_focus="ML version", backend_focus="Backend version"),
        )
        assert b.variations.ml_focus == "ML version"
        assert b.variations.backend_focus == "Backend version"
        assert b.variations.data_focus is None


class TestExperienceModule:
    def test_defaults(self):
        exp = ExperienceModule(
            id="test", company="Corp", title="Dev", dates="2024"
        )
        assert exp.type == "experience"
        assert exp.enabled is True
        assert exp.bullets == []
        assert exp.skills == []
        assert exp.priority == 1

    def test_disabled_entry(self):
        exp = ExperienceModule(
            id="test", company="Corp", title="Dev", dates="2024", enabled=False
        )
        assert exp.enabled is False


class TestEducationModule:
    def test_defaults(self):
        edu = EducationModule(
            id="test", institution="Uni", degree="BSc", dates="2020"
        )
        assert edu.type == "education"
        assert edu.gpa is None
        assert edu.enabled is True


class TestOtherModule:
    def test_defaults(self):
        oth = OtherModule(
            id="test", organization="Org", title="Event", dates="2023"
        )
        assert oth.type == "other"
        assert oth.enabled is True


class TestProfile:
    def test_profile_assembly(self, sample_profile):
        assert sample_profile.personal.name == "Cesar Ochoa"
        assert len(sample_profile.skills.technical) == 8
        assert len(sample_profile.experience) == 2
        assert len(sample_profile.education) == 1
        assert len(sample_profile.other) == 1

    def test_empty_profile(self, sample_personal, sample_skills):
        p = Profile(personal=sample_personal, skills=sample_skills)
        assert p.experience == []
        assert p.education == []
        assert p.other == []


class TestTailoredProfile:
    def test_minimal(self, sample_personal):
        tp = TailoredProfile(personal=sample_personal)
        assert tp.summary == ""
        assert tp.skills == []
        assert tp.experience == []
        assert tp.job_id == ""

    def test_tailored_entry(self):
        entry = TailoredEntry(
            id="test",
            type="experience",
            title="Dev",
            organization="Corp",
            dates="2024",
            bullets=[TailoredBullet(id="b1", text="Did stuff", relevance_score=0.8)],
        )
        assert len(entry.bullets) == 1
        assert entry.bullets[0].relevance_score == 0.8
