"""Select and rank profile modules for a specific job.

Phase 1: Tag-based selection only.
Phase 2: LLM re-ranking and rewriting.
"""

from tycho.matcher.keywords import extract_keywords
from tycho.models import (
    Bullet,
    EducationModule,
    ExperienceModule,
    Job,
    Language,
    OtherModule,
    Profile,
    TailoredBullet,
    TailoredEntry,
    TailoredProfile,
)


def select_modules(
    profile: Profile,
    job: Job,
    language: str = "en",
    max_bullets_per_entry: int = 4,
) -> TailoredProfile:
    """Select and tailor profile modules for a specific job."""
    job_keywords = set(extract_keywords(job.description, profile))

    # Determine best focus area based on job keywords
    focus = _detect_focus(job_keywords, job.title)

    # Select summary variation
    summary = _select_summary(profile, focus, language)

    # Select top skills relevant to job
    skills = _select_skills(profile, job_keywords)

    # Tailor experience entries
    experience = []
    for exp in profile.experience:
        if not exp.enabled:
            continue
        entry = _tailor_experience(exp, job_keywords, focus, language, max_bullets_per_entry)
        if entry:
            experience.append(entry)

    # Tailor education entries
    education = []
    for edu in profile.education:
        if not edu.enabled:
            continue
        entry = _tailor_education(edu, job_keywords, focus, language, max_bullets_per_entry)
        if entry:
            education.append(entry)

    # Tailor other entries
    other = []
    for oth in profile.other:
        if not oth.enabled:
            continue
        entry = _tailor_other(oth, job_keywords, focus, language, max_bullets_per_entry)
        if entry:
            other.append(entry)

    # Use appropriate phone based on language
    personal = profile.personal

    return TailoredProfile(
        personal=personal,
        summary=summary,
        skills=skills,
        languages=profile.skills.languages,
        experience=experience,
        education=education,
        other=other,
        job_id=job.id,
    )


def _detect_focus(job_keywords: set[str], job_title: str) -> str | None:
    """Detect the best focus area based on job keywords and title."""
    title_lower = job_title.lower()

    ml_indicators = {"pytorch", "tensorflow", "machine learning", "deep learning",
                     "computer vision", "nlp", "onnx", "cuda", "ml"}
    backend_indicators = {"backend", "api", "fastapi", "django", "flask",
                         "microservices", "docker", "kubernetes"}
    data_indicators = {"data science", "data engineer", "analytics", "pandas",
                      "statistics", "data"}

    ml_score = len(job_keywords & ml_indicators) + (2 if "ml" in title_lower or "machine learning" in title_lower else 0)
    backend_score = len(job_keywords & backend_indicators) + (2 if "backend" in title_lower or "software" in title_lower else 0)
    data_score = len(job_keywords & data_indicators) + (2 if "data" in title_lower else 0)

    scores = {"ml_focus": ml_score, "backend_focus": backend_score, "data_focus": data_score}
    best = max(scores, key=scores.get)

    return best if scores[best] > 0 else None


def _select_summary(profile: Profile, focus: str | None, language: str) -> str:
    """Select the best summary variation."""
    summary = profile.personal.summary

    if focus:
        variation = getattr(summary.variations, focus, None)
        if variation:
            return variation

    return summary.default


def _select_skills(profile: Profile, job_keywords: set[str]) -> list[str]:
    """Select and rank skills relevant to the job."""
    scored_skills = []
    for skill in profile.skills.technical:
        name_lower = skill.name.lower()
        # Score: keyword match + tag overlap + inverse priority
        kw_match = 1.0 if name_lower in job_keywords else 0.0
        tag_overlap = len(set(t.lower() for t in skill.tags) & job_keywords) / max(len(skill.tags), 1)
        priority_bonus = (4 - skill.priority) / 3  # priority 1 = 1.0, priority 3 = 0.33

        score = kw_match * 3 + tag_overlap + priority_bonus
        scored_skills.append((skill.name, score))

    scored_skills.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in scored_skills[:15]]


def _score_bullet(bullet: Bullet, job_keywords: set[str]) -> float:
    """Score a bullet by tag overlap with job keywords."""
    if not bullet.tags:
        return 0.0
    tag_overlap = len(set(t.lower() for t in bullet.tags) & job_keywords)
    priority_bonus = (4 - bullet.priority) / 3
    return tag_overlap + priority_bonus


def _get_bullet_text(bullet: Bullet, focus: str | None, language: str) -> str:
    """Get the best text for a bullet based on focus and language."""
    # Try language-specific text
    if language == "es" and bullet.text_es:
        return bullet.text_es

    # Try focus variation
    if focus:
        variation = getattr(bullet.variations, focus, None)
        if variation:
            return variation

    return bullet.text


def _tailor_experience(
    exp: ExperienceModule,
    job_keywords: set[str],
    focus: str | None,
    language: str,
    max_bullets: int,
) -> TailoredEntry:
    """Tailor an experience entry for the job."""
    # Score and select bullets
    scored_bullets = [
        (b, _score_bullet(b, job_keywords)) for b in exp.bullets
    ]
    scored_bullets.sort(key=lambda x: x[1], reverse=True)
    selected = scored_bullets[:max_bullets]

    tailored_bullets = [
        TailoredBullet(
            id=b.id,
            text=_get_bullet_text(b, focus, language),
            relevance_score=score,
        )
        for b, score in selected
    ]

    title = exp.title_es if language == "es" and exp.title_es else exp.title
    dates = exp.dates_es if language == "es" and exp.dates_es else exp.dates
    note = exp.note_es if language == "es" and exp.note_es else exp.note

    return TailoredEntry(
        id=exp.id,
        type="experience",
        title=title,
        organization=exp.company,
        dates=dates,
        location=exp.location,
        note=note,
        skills=exp.skills,
        bullets=tailored_bullets,
    )


def _tailor_education(
    edu: EducationModule,
    job_keywords: set[str],
    focus: str | None,
    language: str,
    max_bullets: int,
) -> TailoredEntry:
    """Tailor an education entry for the job."""
    scored_bullets = [
        (b, _score_bullet(b, job_keywords)) for b in edu.bullets
    ]
    scored_bullets.sort(key=lambda x: x[1], reverse=True)
    selected = scored_bullets[:max_bullets]

    tailored_bullets = [
        TailoredBullet(
            id=b.id,
            text=_get_bullet_text(b, focus, language),
            relevance_score=score,
        )
        for b, score in selected
    ]

    degree = edu.degree_es if language == "es" and edu.degree_es else edu.degree
    dates = edu.dates_es if language == "es" and edu.dates_es else edu.dates
    institution = edu.institution_es if language == "es" and edu.institution_es else edu.institution

    return TailoredEntry(
        id=edu.id,
        type="education",
        title=degree,
        organization=institution,
        dates=dates,
        location=edu.location,
        gpa=edu.gpa,
        skills=edu.skills,
        bullets=tailored_bullets,
    )


def _tailor_other(
    oth: OtherModule,
    job_keywords: set[str],
    focus: str | None,
    language: str,
    max_bullets: int,
) -> TailoredEntry:
    """Tailor an 'other' entry for the job."""
    scored_bullets = [
        (b, _score_bullet(b, job_keywords)) for b in oth.bullets
    ]
    scored_bullets.sort(key=lambda x: x[1], reverse=True)
    selected = scored_bullets[:max_bullets]

    tailored_bullets = [
        TailoredBullet(
            id=b.id,
            text=_get_bullet_text(b, focus, language),
            relevance_score=score,
        )
        for b, score in selected
    ]

    title = oth.title_es if language == "es" and oth.title_es else oth.title
    dates = oth.dates_es if language == "es" and oth.dates_es else oth.dates

    return TailoredEntry(
        id=oth.id,
        type="other",
        title=title,
        organization=oth.organization,
        dates=dates,
        location=oth.location,
        skills=oth.skills,
        bullets=tailored_bullets,
    )
