# Gemini Context: Tycho — Automated Job Application Platform

Tycho is a sophisticated tool for automating the job search process. it scrapes job postings, scores them against a highly modular YAML-based profile, and generates tailored CVs in LaTeX/PDF format. It is designed to be local-first, leveraging SQLite for storage and Jinja2 for flexible template rendering.

## Project Overview

- **Purpose**: Automate job scraping, matching, and CV tailoring.
- **Key Features**:
    - Concurrent scraping of LinkedIn and Indeed via `python-jobspy`.
    - Modular YAML profile system (one file per experience/education entry).
    - Weighted scoring algorithm based on keywords, titles, skills, and location.
    - Focus area detection (e.g., ML vs. Backend) for smart bullet selection.
    - Bilingual support (English/Spanish) for profiles and generated CVs.
    - ATS-friendly LaTeX templates.
- **Architecture**:
    - `src/tycho/collector`: Scrapers and normalization logic.
    - `src/tycho/matcher`: Keyword extraction and multi-factor scoring.
    - `src/tycho/cv`: Profile assembly, focus-based tailoring, and LaTeX/PDF compilation.
    - `src/tycho/models.py`: Unified Pydantic models for jobs, profiles, and tailoring.

## Technologies

- **Language**: Python 3.11+
- **CLI**: Typer + Rich for an interactive and polished terminal experience.
- **Database**: SQLite via SQLAlchemy (local-first storage).
- **Matching/Scoring**: Pydantic for validation and Pydantic-Settings for configuration.
- **Templating**: Jinja2 with custom delimiters (`<% %>` for blocks) to avoid LaTeX conflicts.
- **Scraping**: `python-jobspy` (specialized for LinkedIn/Indeed).
- **Environment/Build**: `uv` for fast package management, `hatchling` as the build backend.

## Building and Running

### Setup
The project uses `uv` for environment management.
```bash
uv venv && uv pip install -e . --python .venv/bin/python
source .venv/bin/activate
```

### Core Commands
- `tycho collect`: Scrape jobs from LinkedIn/Indeed based on `config.yaml`.
- `tycho profile`: Validate the modular YAML files in the `profile/` directory.
- `tycho jobs`: List collected jobs with scores and statuses.
- `tycho show <id>`: Detailed view of a job, its description, and score breakdown.
- `tycho generate <id>`: Generate a tailored CV (PDF/Tex). Use `--lang es` for Spanish.
- `tycho dashboard`: High-level summary of job application progress and top matches.
- `tycho mark <id> <status>`: Update job status (e.g., `interested`, `applied`).

## Development Conventions

- **Modular Profiles**: Profile data is split into small YAML files in `profile/`. Each entry (experience, education, etc.) should have its own file for clean version control.
- **Tag-Based Tailoring**: Use `tags` in profile bullets to match against keywords extracted from job descriptions.
- **Focus Areas**: The system currently detects `ml_focus`, `backend_focus`, and `data_focus`. When adding new bullets, provide variations for these focuses in the `variations` field.
- **Testing**: Tests are located in the `tests/` directory and use `pytest`. Run with `pytest`.
- **Formatting**: Adheres to standard Python formatting (likely `ruff` or `black`, though not explicitly configured in `pyproject.toml`).

## Directory Structure Highlights
- `src/tycho/`: Core application logic.
- `profile/`: User profile data and LaTeX templates.
- `output/`: Generated CVs (ignored by git).
- `CVs/`: Legacy or reference CV files.
- `plans/`: Documentation on project evolution and future phases.
- `config.yaml`: Global settings for search, scoring, and LLM integration.
