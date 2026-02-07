"""Shared test fixtures for Tycho."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from tycho.config import ScoringConfig
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


@pytest.fixture
def sample_personal():
    return PersonalInfo(
        name="Cesar Ochoa",
        name_es="César Ochoa Munárriz",
        email="caeochoa@gmail.com",
        phone_uk="+44 792 393 6908",
        phone_es="+34 636 382 118",
        linkedin="linkedin.com/in/caeochoa",
        titles=["AI Engineer", "MSc Design Informatics", "BSc Mathematics"],
        titles_es=["Ingeniero de IA", "MSc Design Informatics", "BSc Mathematics"],
        summary=Summary(
            default="AI Engineer with experience in RAG systems.",
            variations=SummaryVariations(
                ml_focus="ML Engineer specializing in PyTorch and CV.",
                backend_focus="Software Engineer with Python backend skills.",
                data_focus="Data Scientist with mathematics background.",
            ),
        ),
        hobbies=["Climbing", "Meditation"],
        hobbies_es=["Escalada", "Meditación"],
    )


@pytest.fixture
def sample_skills():
    return SkillsData(
        technical=[
            Skill(name="Python", tags=["all"], priority=1),
            Skill(name="PyTorch", tags=["ml", "ai", "cv"], priority=1),
            Skill(name="LangChain", tags=["ai", "llm", "rag"], priority=1),
            Skill(name="ONNX", tags=["ml", "cv", "optimization"], priority=2),
            Skill(name="CUDA", tags=["ml", "cv", "optimization"], priority=2),
            Skill(name="SQL", tags=["all", "data", "backend"], priority=1),
            Skill(name="React", tags=["web", "frontend"], priority=2),
            Skill(name="Docker", tags=["devops", "cloud"], priority=3),
        ],
        languages=[
            Language(language="English", level="Proficient", level_es="Experto"),
            Language(language="Spanish", level="Native", level_es="Nativo"),
        ],
    )


@pytest.fixture
def sample_experience():
    return [
        ExperienceModule(
            id="oesia_ai_engineer",
            type="experience",
            company="Grupo Oesía",
            title="AI Engineer",
            title_es="Ingeniero de IA",
            dates="2024 - Present",
            dates_es="2024 - Presente",
            location="Madrid, Spain",
            priority=1,
            tags=["ai", "ml", "python", "rag"],
            skills=["Python", "LangChain", "PyTorch"],
            bullets=[
                Bullet(
                    id="oesia_rag",
                    text="Led backend development of OKM, a no-code RAG platform.",
                    text_es="Desarrollo del backend de OKM.",
                    tags=["rag", "llm", "python"],
                    priority=1,
                    variations=BulletVariations(
                        ml_focus="Architected RAG pipeline using LangChain.",
                        backend_focus="Built full-stack no-code platform.",
                    ),
                ),
                Bullet(
                    id="oesia_cv",
                    text="Optimized computer vision models achieving 3x speedup.",
                    text_es="Optimicé modelos de visión por computador.",
                    tags=["cv", "optimization", "onnx", "cuda"],
                    priority=1,
                    variations=BulletVariations(
                        ml_focus="Reduced CV model inference time through ONNX optimization.",
                    ),
                ),
            ],
        ),
        ExperienceModule(
            id="acturis_analyst",
            type="experience",
            company="Acturis",
            title="Technical Business Analyst",
            dates="2022 - 2024",
            location="London, UK",
            priority=2,
            tags=["web", "frontend", "sql"],
            skills=["HTML", "CSS", "JavaScript", "React", "SQL"],
            bullets=[
                Bullet(
                    id="acturis_projects",
                    text="Led and managed over 20 projects end-to-end.",
                    tags=["project-management"],
                    priority=1,
                ),
            ],
        ),
    ]


@pytest.fixture
def sample_education():
    return [
        EducationModule(
            id="edinburgh_msc",
            type="education",
            institution="The University of Edinburgh",
            degree="MSc Design Informatics",
            degree_es="MSc Design Informatics",
            dates="2021 - 2022",
            gpa="3.7/4",
            priority=1,
            tags=["ml", "ai", "xai"],
            skills=["Python", "PyTorch", "NumPy"],
            bullets=[
                Bullet(
                    id="edinburgh_ml",
                    text="Utilized Python and PyTorch for ML.",
                    tags=["ml", "python"],
                    priority=1,
                ),
            ],
        ),
    ]


@pytest.fixture
def sample_other():
    return [
        OtherModule(
            id="genai_hackathon",
            type="other",
            organization="Newspeak House",
            title="London's 24hr GenAI Hackathon",
            title_es="Hackathon de GenAI de 24h de Londres",
            dates="2023",
            priority=1,
            tags=["ai", "llm", "web"],
            skills=["JavaScript", "React", "LangChain"],
            bullets=[
                Bullet(
                    id="genai_app",
                    text="Developed an educational app with voice recognition and GenAI.",
                    text_es="Desarrollo de una aplicación educativa con IA generativa.",
                    tags=["ai", "llm", "web"],
                    priority=1,
                ),
            ],
        ),
    ]


@pytest.fixture
def sample_profile(sample_personal, sample_skills, sample_experience, sample_education, sample_other):
    return Profile(
        personal=sample_personal,
        skills=sample_skills,
        experience=sample_experience,
        education=sample_education,
        other=sample_other,
    )


@pytest.fixture
def ml_job():
    return Job(
        id="job-ml-001",
        source="indeed",
        source_id="indeed_ml_001",
        title="Senior Machine Learning Engineer",
        company="DeepTech AI",
        location="Madrid, Spain",
        description=(
            "We are looking for a Senior ML Engineer with experience in "
            "PyTorch, ONNX optimization, computer vision, and RAG systems. "
            "Must have Python expertise and experience with cloud platforms. "
            "LangChain experience is a plus. Deep learning and CUDA required."
        ),
        url="https://example.com/job/ml",
        date_posted=datetime(2025, 1, 15),
        status=JobStatus.NEW,
    )


@pytest.fixture
def backend_job():
    return Job(
        id="job-be-001",
        source="linkedin",
        source_id="linkedin_be_001",
        title="Backend Software Engineer",
        company="WebCorp Ltd",
        location="London, UK",
        description=(
            "Looking for a backend engineer experienced with Python, FastAPI, "
            "Docker, Kubernetes, PostgreSQL, REST APIs, and microservices."
        ),
        url="https://example.com/job/be",
        date_posted=datetime(2025, 1, 20),
        status=JobStatus.NEW,
    )


@pytest.fixture
def empty_job():
    return Job(
        id="job-empty-001",
        source="test",
        source_id="test_empty",
        title="",
        company="Unknown",
        location="",
        description="",
    )


@pytest.fixture
def scoring_config():
    return ScoringConfig()


@pytest.fixture
def profile_dir(tmp_path, sample_personal, sample_skills, sample_experience, sample_education, sample_other):
    """Create a temporary profile directory with YAML files."""
    # personal.yaml
    personal_data = {
        "name": sample_personal.name,
        "name_es": sample_personal.name_es,
        "email": sample_personal.email,
        "phone_uk": sample_personal.phone_uk,
        "phone_es": sample_personal.phone_es,
        "linkedin": sample_personal.linkedin,
        "titles": sample_personal.titles,
        "titles_es": sample_personal.titles_es,
        "summary": {
            "default": sample_personal.summary.default,
            "variations": {
                "ml_focus": sample_personal.summary.variations.ml_focus,
                "backend_focus": sample_personal.summary.variations.backend_focus,
                "data_focus": sample_personal.summary.variations.data_focus,
            },
        },
        "hobbies": sample_personal.hobbies,
        "hobbies_es": sample_personal.hobbies_es,
    }
    (tmp_path / "personal.yaml").write_text(yaml.dump(personal_data, allow_unicode=True))

    # skills.yaml
    skills_data = {
        "technical": [{"name": s.name, "tags": s.tags, "priority": s.priority} for s in sample_skills.technical],
        "languages": [{"language": l.language, "level": l.level, "level_es": l.level_es} for l in sample_skills.languages],
    }
    (tmp_path / "skills.yaml").write_text(yaml.dump(skills_data, allow_unicode=True))

    # experience/
    exp_dir = tmp_path / "experience"
    exp_dir.mkdir()
    for exp in sample_experience:
        data = {
            "id": exp.id,
            "type": exp.type,
            "company": exp.company,
            "title": exp.title,
            "title_es": exp.title_es,
            "dates": exp.dates,
            "dates_es": exp.dates_es,
            "location": exp.location,
            "priority": exp.priority,
            "tags": exp.tags,
            "skills": exp.skills,
            "bullets": [
                {
                    "id": b.id,
                    "text": b.text,
                    "text_es": b.text_es,
                    "tags": b.tags,
                    "priority": b.priority,
                    "variations": {k: v for k, v in b.variations.model_dump().items() if v is not None},
                }
                for b in exp.bullets
            ],
        }
        (exp_dir / f"{exp.id}.yaml").write_text(yaml.dump(data, allow_unicode=True))

    # education/
    edu_dir = tmp_path / "education"
    edu_dir.mkdir()
    for edu in sample_education:
        data = {
            "id": edu.id,
            "type": edu.type,
            "institution": edu.institution,
            "degree": edu.degree,
            "degree_es": edu.degree_es,
            "dates": edu.dates,
            "gpa": edu.gpa,
            "priority": edu.priority,
            "tags": edu.tags,
            "skills": edu.skills,
            "bullets": [
                {"id": b.id, "text": b.text, "tags": b.tags, "priority": b.priority}
                for b in edu.bullets
            ],
        }
        (edu_dir / f"{edu.id}.yaml").write_text(yaml.dump(data, allow_unicode=True))

    # other/
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    for oth in sample_other:
        data = {
            "id": oth.id,
            "type": oth.type,
            "organization": oth.organization,
            "title": oth.title,
            "title_es": oth.title_es,
            "dates": oth.dates,
            "priority": oth.priority,
            "tags": oth.tags,
            "skills": oth.skills,
            "bullets": [
                {"id": b.id, "text": b.text, "text_es": b.text_es, "tags": b.tags, "priority": b.priority}
                for b in oth.bullets
            ],
        }
        (other_dir / f"{oth.id}.yaml").write_text(yaml.dump(data, allow_unicode=True))

    return tmp_path
