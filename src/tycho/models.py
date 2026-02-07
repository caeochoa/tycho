"""Pydantic data models for Tycho."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# --- Job Models ---

class JobStatus(str, Enum):
    NEW = "new"
    REVIEWED = "reviewed"
    INTERESTED = "interested"
    APPLIED = "applied"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class Job(BaseModel):
    """A collected job posting."""
    id: str
    source: str
    source_id: str = ""
    title: str
    company: str
    location: str = ""
    description: str = ""
    url: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    date_posted: datetime | None = None
    date_collected: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)
    score: float | None = None
    score_details: dict | None = None
    status: JobStatus = JobStatus.NEW
    cv_path: str | None = None
    cover_letter_path: str | None = None
    notes: str | None = None


# --- Profile Models ---

class BulletVariations(BaseModel):
    """Optional bullet text variations keyed by focus area."""
    ml_focus: str | None = None
    backend_focus: str | None = None
    data_focus: str | None = None


class Bullet(BaseModel):
    """A single bullet point within a profile module."""
    id: str
    text: str
    text_es: str = ""
    tags: list[str] = Field(default_factory=list)
    priority: int = 1
    variations: BulletVariations = BulletVariations()


class ExperienceModule(BaseModel):
    """A work experience entry."""
    id: str
    type: str = "experience"
    company: str
    title: str
    title_es: str = ""
    dates: str
    dates_es: str = ""
    location: str = ""
    note: str | None = None
    note_es: str | None = None
    priority: int = 1
    tags: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)
    enabled: bool = True


class EducationModule(BaseModel):
    """An education entry."""
    id: str
    type: str = "education"
    institution: str
    institution_es: str | None = None
    degree: str
    degree_es: str = ""
    dates: str
    dates_es: str = ""
    location: str = ""
    gpa: str | None = None
    priority: int = 1
    tags: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)
    enabled: bool = True


class OtherModule(BaseModel):
    """A non-work, non-education entry (hackathon, leadership, etc.)."""
    id: str
    type: str = "other"
    organization: str
    title: str
    title_es: str = ""
    dates: str
    dates_es: str = ""
    location: str = ""
    priority: int = 1
    tags: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)
    enabled: bool = True


class Skill(BaseModel):
    """A technical skill."""
    name: str
    tags: list[str] = Field(default_factory=list)
    priority: int = 1


class Language(BaseModel):
    """A spoken language."""
    language: str
    level: str
    level_es: str = ""


class SummaryVariations(BaseModel):
    """Summary text variations keyed by focus area."""
    ml_focus: str | None = None
    backend_focus: str | None = None
    data_focus: str | None = None


class Summary(BaseModel):
    """Professional summary with variations."""
    default: str = ""
    variations: SummaryVariations = SummaryVariations()


class PersonalInfo(BaseModel):
    """Personal identity and contact info."""
    name: str
    name_es: str = ""
    email: str
    phone_uk: str = ""
    phone_es: str = ""
    linkedin: str = ""
    titles: list[str] = Field(default_factory=list)
    titles_es: list[str] = Field(default_factory=list)
    summary: Summary = Summary()
    hobbies: list[str] = Field(default_factory=list)
    hobbies_es: list[str] = Field(default_factory=list)


class SkillsData(BaseModel):
    """All skills and languages."""
    technical: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)


class Profile(BaseModel):
    """The complete assembled profile."""
    personal: PersonalInfo
    skills: SkillsData
    experience: list[ExperienceModule] = Field(default_factory=list)
    education: list[EducationModule] = Field(default_factory=list)
    other: list[OtherModule] = Field(default_factory=list)


# --- Tailored Profile Models ---

class TailoredBullet(BaseModel):
    """A bullet selected/tailored for a specific job."""
    id: str
    text: str
    relevance_score: float = 0.0


class TailoredEntry(BaseModel):
    """A profile entry tailored for a specific job."""
    id: str
    type: str
    title: str
    organization: str  # company or institution
    dates: str
    location: str = ""
    note: str | None = None
    gpa: str | None = None
    skills: list[str] = Field(default_factory=list)
    bullets: list[TailoredBullet] = Field(default_factory=list)


class TailoredProfile(BaseModel):
    """A profile tailored for a specific job application."""
    personal: PersonalInfo
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    experience: list[TailoredEntry] = Field(default_factory=list)
    education: list[TailoredEntry] = Field(default_factory=list)
    other: list[TailoredEntry] = Field(default_factory=list)
    job_id: str = ""
    focus: str | None = None


# --- LLM Models ---

class LLMKeywordResult(BaseModel):
    """Result from LLM keyword extraction."""
    keywords: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    focus_area: str | None = None


# --- Cover Letter Models ---

class CoverLetter(BaseModel):
    """A generated cover letter."""
    job_id: str
    greeting: str = "Dear Hiring Manager,"
    paragraphs: list[str] = Field(default_factory=list)
    closing: str = "Sincerely,"
    language: str = "en"

    @property
    def full_text(self) -> str:
        """Assemble the complete cover letter."""
        parts = [self.greeting, ""]
        for para in self.paragraphs:
            parts.append(para)
            parts.append("")
        parts.append(self.closing)
        return "\n".join(parts)
