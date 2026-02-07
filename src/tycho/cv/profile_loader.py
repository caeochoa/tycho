"""Load and assemble multi-file YAML profile into Pydantic models."""

from pathlib import Path

import yaml

from tycho.models import (
    Bullet,
    EducationModule,
    ExperienceModule,
    Language,
    OtherModule,
    PersonalInfo,
    Profile,
    Skill,
    SkillsData,
    Summary,
    SummaryVariations,
    BulletVariations,
)


def load_profile(profile_dir: str | Path) -> Profile:
    """Load the full profile from the multi-file YAML structure."""
    profile_dir = Path(profile_dir)

    personal = _load_personal(profile_dir / "personal.yaml")
    skills = _load_skills(profile_dir / "skills.yaml")
    experience = _load_modules(profile_dir / "experience", ExperienceModule)
    education = _load_modules(profile_dir / "education", EducationModule)
    other = _load_modules(profile_dir / "other", OtherModule)

    # Sort by priority
    experience.sort(key=lambda x: x.priority)
    education.sort(key=lambda x: x.priority)
    other.sort(key=lambda x: x.priority)

    return Profile(
        personal=personal,
        skills=skills,
        experience=experience,
        education=education,
        other=other,
    )


def _load_yaml(path: Path) -> dict:
    """Load a YAML file."""
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _load_personal(path: Path) -> PersonalInfo:
    """Load personal.yaml into PersonalInfo."""
    data = _load_yaml(path)

    summary_data = data.get("summary", {})
    variations_data = summary_data.get("variations", {})
    summary = Summary(
        default=summary_data.get("default", ""),
        variations=SummaryVariations(**variations_data),
    )
    data["summary"] = summary

    return PersonalInfo(**data)


def _load_skills(path: Path) -> SkillsData:
    """Load skills.yaml into SkillsData."""
    data = _load_yaml(path)

    technical = [Skill(**s) for s in data.get("technical", [])]
    languages = [Language(**l) for l in data.get("languages", [])]

    return SkillsData(technical=technical, languages=languages)


def _load_modules(directory: Path, model_class: type) -> list:
    """Load all YAML files from a directory into a list of models."""
    if not directory.exists():
        return []

    modules = []
    for yaml_file in sorted(directory.glob("*.yaml")):
        data = _load_yaml(yaml_file)
        if data.get("enabled", True) is False:
            continue

        # Parse bullets
        bullets_data = data.get("bullets", [])
        bullets = []
        for b in bullets_data:
            variations = b.pop("variations", {})
            bullet = Bullet(**b, variations=BulletVariations(**variations))
            bullets.append(bullet)
        data["bullets"] = bullets

        modules.append(model_class(**data))

    return modules


def validate_profile(profile_dir: str | Path) -> list[str]:
    """Validate all profile YAML files. Returns list of errors (empty = valid)."""
    errors = []
    profile_dir = Path(profile_dir)

    # Check required files
    for required in ["personal.yaml", "skills.yaml"]:
        path = profile_dir / required
        if not path.exists():
            errors.append(f"Missing required file: {path}")

    # Check directories
    for subdir in ["experience", "education"]:
        path = profile_dir / subdir
        if not path.exists():
            errors.append(f"Missing directory: {path}")
        elif not list(path.glob("*.yaml")):
            errors.append(f"No YAML files in: {path}")

    # Try loading the full profile
    if not errors:
        try:
            load_profile(profile_dir)
        except Exception as e:
            errors.append(f"Failed to load profile: {e}")

    return errors
