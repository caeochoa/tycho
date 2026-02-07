# Tycho — Automated Job Application Platform

## Context

Cesar has two LaTeX CVs (EN/ES) using a custom `developercv.cls` template that has significant ATS compatibility issues (profile photos, FontAwesome icons, multi-column layouts). He wants a system that:
1. Collects job postings from LinkedIn and Indeed
2. Scores and ranks them against his profile
3. Generates tailored CVs (.docx for ATS + LaTeX PDF for recruiters) using modular content
4. Drafts cover letters with LLMs
5. Presents a curated dashboard for him to review and decide which to apply to

This plan defines a 3-phase roadmap (PoC → MVP → Full) where each phase delivers standalone value.

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CV output | Dual: .docx + LaTeX PDF | .docx is safest for ATS; LaTeX PDF for direct recruiter contact |
| Job sources | LinkedIn + Indeed via JobSpy | JobSpy scrapes both concurrently; Indeed has no rate limits |
| LLM abstraction | LangChain (multi-provider) | Supports Claude, OpenAI, Ollama; avoids vendor lock-in |
| Automation level | Curated (human-in-the-loop) | Quality over quantity; no risky browser automation |
| CV data format | Multi-file YAML modules (manual curation) | One file per experience/entry; extensible, clean diffs, versionable |
| Storage | SQLite + file-based config | Local-first, portable, zero infrastructure |
| UI | CLI-first, web dashboard in Phase 3 | Fast to build; Rich library for terminal UI |

---

## Project Structure

```
tycho/
├── pyproject.toml              # Project config (uv/poetry, dependencies)
├── config.yaml                 # User preferences (search terms, locations, weights, LLM config)
├── profile/
│   ├── personal.yaml           # Personal info, contact details, summary variations
│   ├── skills.yaml             # Technical skills, languages (with tags & priorities)
│   ├── experience/             # One YAML file per work experience entry
│   │   ├── oesia_ai_engineer.yaml
│   │   ├── acturis_analyst.yaml
│   │   └── edinburgh_vision.yaml
│   ├── education/              # One YAML file per education entry
│   │   ├── edinburgh_msc.yaml
│   │   ├── manchester_bsc.yaml
│   │   └── sek_ib.yaml
│   ├── other/                  # Hackathons, leadership, certifications
│   │   ├── genai_hackathon.yaml
│   │   └── public_speaking.yaml
│   └── templates/
│       ├── ats_resume.tex.j2   # ATS-friendly LaTeX Jinja2 template
│       ├── ats_resume_es.tex.j2
│       └── resume.docx.j2     # python-docx template definition
├── src/
│   └── tycho/
│       ├── __init__.py
│       ├── cli.py              # Typer CLI entry point
│       ├── config.py           # Config loading (Pydantic settings)
│       ├── models.py           # Pydantic data models (Job, Profile, Module, etc.)
│       ├── db.py               # SQLite via SQLAlchemy (job storage, application tracking)
│       ├── collector/
│       │   ├── __init__.py
│       │   ├── base.py         # Abstract collector interface
│       │   ├── jobspy_collector.py  # JobSpy integration (LinkedIn + Indeed)
│       │   └── normalize.py    # Job data normalization & deduplication
│       ├── matcher/
│       │   ├── __init__.py
│       │   ├── scorer.py       # Job-profile scoring algorithm
│       │   └── keywords.py     # Keyword extraction from job descriptions
│       ├── cv/
│       │   ├── __init__.py
│       │   ├── profile_loader.py   # Load & assemble multi-file YAML profile
│       │   ├── module_selector.py  # Select/rank modules for a job
│       │   ├── latex_builder.py    # Jinja2 → LaTeX → PDF compilation
│       │   └── docx_builder.py     # python-docx generation
│       ├── cover_letter/
│       │   ├── __init__.py
│       │   └── generator.py    # LLM-based cover letter drafting
│       └── llm/
│           ├── __init__.py
│           └── client.py       # LangChain LLM abstraction
├── output/                     # Generated CVs, cover letters, exports
├── tests/
└── alembic/                    # DB migrations (Phase 3)
```

---

## Data Models

### Multi-File CV Module System

The profile is split across multiple files for extensibility and clean version control.

**`profile/personal.yaml`** — Identity, contact, summaries:
```yaml
name: "Cesar Ochoa"
name_es: "César Ochoa Munárriz"
email: "caeochoa@gmail.com"
phone_uk: "+44 792 393 6908"
phone_es: "+34 636 382 118"
linkedin: "linkedin.com/in/caeochoa"
titles: ["AI Engineer", "MSc Design Informatics", "BSc Mathematics"]

summary:
  default: "AI Engineer with experience in RAG systems, computer vision, and ML pipelines..."
  variations:
    ml_focus: "Machine Learning Engineer specializing in PyTorch, computer vision optimization..."
    backend_focus: "Software Engineer with strong Python backend and cloud infrastructure skills..."
    data_focus: "Data Scientist with mathematics background and hands-on ML experience..."
```

**`profile/skills.yaml`** — Skills with tags and priorities:
```yaml
technical:
  - name: "Python"
    tags: ["all"]
    priority: 1
  - name: "PyTorch"
    tags: ["ml", "ai", "cv"]
    priority: 1
  # ...
languages:
  - language: "English"
    level: "Proficient"
  - language: "Spanish"
    level: "Native"
```

**`profile/experience/oesia_ai_engineer.yaml`** — One file per experience:
```yaml
id: "oesia_ai_engineer"
type: "experience"          # experience | education | other
company: "Grupo Oesía"
title: "AI Engineer"
title_es: "Ingeniero de IA"
dates: "2024 - Present"
location: "Madrid, Spain"
priority: 1                 # Ordering weight (lower = more important)
tags: ["ai", "ml", "python", "rag", "cv", "cloud"]
skills: ["Python", "LangChain", "PyTorch", "ONNX", "CUDA", "Azure", "SQL"]

bullets:
  - id: "oesia_rag"
    text: "Developed OKM, a no-code RAG platform enabling clients to build custom knowledge retrieval systems"
    text_es: "Desarrollé OKM, una plataforma RAG sin código..."
    tags: ["rag", "llm", "python"]
    priority: 1
    variations:
      ml_focus: "Architected RAG pipeline using LangChain and vector databases for enterprise knowledge retrieval"
      backend_focus: "Built full-stack no-code platform with Python backend serving RAG-based document retrieval"

  - id: "oesia_cv"
    text: "Optimized computer vision models achieving 3x inference speedup via ONNX/CUDA optimization"
    text_es: "Optimicé modelos de visión por computador..."
    tags: ["cv", "optimization", "onnx", "cuda"]
    priority: 1
    variations:
      ml_focus: "Reduced CV model inference time by 70% through ONNX graph optimization and CUDA kernel tuning"
```

**`profile/education/edinburgh_msc.yaml`** — Same schema, different `type`:
```yaml
id: "edinburgh_msc"
type: "education"
institution: "University of Edinburgh"
degree: "MSc Design Informatics"
dates: "2021 - 2022"
gpa: "3.7/4"
priority: 1
tags: ["ml", "ai", "xai", "research"]
skills: ["Python", "PyTorch", "NumPy", "Machine Learning", "xAI"]

bullets:
  - id: "edinburgh_dissertation"
    text: "Dissertation: Explainable AI methods for neural network interpretability"
    tags: ["xai", "ml", "research"]
    priority: 1
```

**Benefits of this structure**:
- Add a new experience by dropping in a new `.yaml` file — no other files change
- Each module is self-contained with its own bullets, tags, variations, and translations
- Git diffs are clean (one file per change)
- LLMs can process individual modules without loading the full profile
- Easy to disable a module by moving it to a `_disabled/` folder or adding `enabled: false`

### SQLite Schema (via SQLAlchemy)

```python
class Job(Base):
    id: str               # UUID
    source: str           # "linkedin" | "indeed"
    source_id: str        # Original platform ID
    title: str
    company: str
    location: str
    description: str
    url: str
    salary_min: float | None
    salary_max: float | None
    date_posted: datetime
    date_collected: datetime
    tags: str             # JSON array of extracted keywords
    score: float | None   # Match score (0-1)
    score_details: str | None  # JSON breakdown
    status: str           # "new" | "reviewed" | "interested" | "applied" | "rejected" | "archived"
    cv_path: str | None   # Path to generated CV
    cover_letter_path: str | None
    notes: str | None
    # Unique constraint on (source, source_id) for deduplication
```

### `config.yaml`

```yaml
search:
  terms: ["AI Engineer", "Machine Learning Engineer", "Python Developer"]
  locations: ["Remote", "Madrid", "London", "Edinburgh"]
  country: "Spain"  # or "UK", affects which phone/language to use
  results_per_source: 50

scoring:
  weights:
    keyword_match: 0.35
    title_match: 0.25
    skills_overlap: 0.25
    location_match: 0.15
  thresholds:
    high_interest: 0.75    # Highlighted in dashboard
    low_interest: 0.30     # Hidden by default

llm:
  provider: "anthropic"    # or "openai", "ollama"
  model: "claude-sonnet-4-5-20250929"
  temperature: 0.3
  # LangChain will handle provider switching

output:
  formats: ["docx", "pdf"]  # Which formats to generate
  language: "en"             # or "es", or "both"
```

---

## Component Design

### 1. Job Collection (`collector/`)

**`jobspy_collector.py`**: Wraps the JobSpy library.

```python
def collect_jobs(search_terms: list[str], locations: list[str],
                 sources: list[str] = ["linkedin", "indeed"],
                 results_wanted: int = 50) -> list[Job]:
    """Collect jobs from configured sources via JobSpy."""
    # Uses jobspy.scrape_jobs() for each (term, location) pair
    # Returns normalized Job models
```

**`normalize.py`**: Deduplication by (company_normalized, title_normalized, location_normalized) hash. Merges duplicates, keeping the richest description.

### 2. Matching & Scoring (`matcher/`)

**`keywords.py`**: Extract keywords from job description using:
- Phase 1: Simple TF-IDF / regex pattern matching against known skill lists
- Phase 2: LLM-based extraction (structured output via LangChain)

**`scorer.py`**: Score = weighted sum of:
- `keyword_match` (0.35): % of job keywords found in profile skills
- `title_match` (0.25): Similarity between job title and profile titles/experience
- `skills_overlap` (0.25): Jaccard similarity of job required skills vs profile skills
- `location_match` (0.15): Binary match against preferred locations

All weights configurable in `config.yaml`.

### 3. CV Generation (`cv/`)

**`profile_loader.py`**: Scans `profile/` directory, loads `personal.yaml`, `skills.yaml`, and all module files from `experience/`, `education/`, `other/` into Pydantic models. Assembles them into a unified `Profile` object.

**`module_selector.py`**: Given a Job, selects which bullets/variations to include:
- Phase 1: Tag-based selection (match bullet tags to job keywords)
- Phase 2: LLM re-ranking (ask LLM to rank bullets by relevance to job description)

```python
def select_modules(profile: Profile, job: Job, max_bullets_per_entry: int = 4) -> TailoredProfile:
    """Select and optionally rewrite profile modules for a specific job."""
    # 1. Extract job keywords
    # 2. Score each bullet by tag overlap with job keywords
    # 3. Select top bullets per experience entry
    # 4. Choose variation closest to job type (ml_focus, backend_focus, etc.)
    # 5. (Phase 2) LLM re-ranks and optionally rewrites
    return TailoredProfile(...)
```

**`latex_builder.py`**: Uses Jinja2 to render `ats_resume.tex.j2` with the tailored profile, then compiles to PDF via `pdflatex`/`latexmk`.

**`docx_builder.py`**: Uses `python-docx` to generate a clean .docx from the tailored profile. Standard fonts (Calibri), clear headings, no images.

### 4. Cover Letter (`cover_letter/`)

**`generator.py`**: LangChain-based generation.

```python
def generate_cover_letter(job: Job, profile: Profile, language: str = "en") -> str:
    """Generate a tailored cover letter draft."""
    # Prompt includes: job description, selected profile modules,
    # company context, role requirements
    # Output: structured cover letter (greeting, 3 paragraphs, closing)
```

### 5. LLM Client (`llm/`)

**`client.py`**: Thin wrapper around LangChain.

```python
def get_llm(config: LLMConfig) -> BaseChatModel:
    """Get configured LLM via LangChain."""
    # Returns ChatAnthropic, ChatOpenAI, or ChatOllama based on config
```

### 6. CLI (`cli.py`)

Built with Typer + Rich for terminal UI.

```
tycho collect              # Run job collection
tycho jobs                 # List collected jobs (table with scores)
tycho jobs --status new    # Filter by status
tycho show <job_id>        # Show job details + match breakdown
tycho generate <job_id>    # Generate tailored CV + cover letter for a job
tycho generate <job_id> --format docx,pdf --lang en
tycho batch-generate       # Generate materials for all "interested" jobs
tycho mark <job_id> <status>  # Mark job as interested/rejected/applied
tycho dashboard            # Interactive Rich dashboard (browse, filter, act)
tycho config               # Show/edit config
tycho profile              # Validate all profile YAML modules
```

---

## ATS-Friendly LaTeX Template Design

The new `ats_resume.tex.j2` template will:
- Use `article` document class (not custom class)
- Use `lmodern` font (standard, machine-readable)
- Single-column layout throughout
- `\pdfgentounicode=1` for Unicode text extraction
- Standard section headings via `titlesec` (no colored boxes)
- Simple bullet lists via `itemize` (no custom bullets)
- No images, no FontAwesome, no TikZ
- Contact info as plain text (no icons)
- Hyperlinks via `hyperref` with visible text
- Jinja2 templating for dynamic content insertion

Reference templates: Rover Resume, Overleaf ATS templates.

---

## Phased Roadmap

### Phase 1 — PoC (Proof of Concept)
**Goal**: Collect jobs, browse them in CLI, generate a basic tailored CV PDF.

**Build**:
1. Project scaffolding (`pyproject.toml`, directory structure, dependencies)
2. `config.yaml` + `config.py` (Pydantic settings loader)
3. `models.py` (Pydantic models for Job, Profile, Bullet, etc.)
4. `profile/personal.yaml`, `profile/skills.yaml`, `profile/experience/*.yaml`, `profile/education/*.yaml` (manually curate from existing LaTeX CVs)
5. `db.py` (SQLAlchemy + SQLite setup, Job table)
6. `jobspy_collector.py` (collect jobs from LinkedIn + Indeed)
7. `normalize.py` (dedup, normalize job data)
8. `profile_loader.py` (load YAML into Pydantic models)
9. `module_selector.py` — **tag-based only** (no LLM yet)
10. `ats_resume.tex.j2` (ATS-friendly LaTeX template)
11. `latex_builder.py` (Jinja2 render + pdflatex compile)
12. `cli.py` — commands: `collect`, `jobs`, `show`, `generate`, `mark`, `profile`

**Deliverable**: Run `tycho collect` → `tycho jobs` → `tycho show <id>` → `tycho generate <id>` and get a tailored PDF CV.

**Dependencies**: `jobspy`, `sqlalchemy`, `pydantic`, `pydantic-settings`, `typer`, `rich`, `jinja2`, `pyyaml`

### Phase 2 — MVP
**Goal**: Add LLM intelligence, .docx output, cover letters, and scoring.

**Build**:
1. `llm/client.py` (LangChain multi-provider setup)
2. `keywords.py` — LLM-based keyword extraction from job descriptions
3. `scorer.py` (weighted scoring algorithm)
4. Update `module_selector.py` — LLM re-ranking of bullets + variation selection
5. `docx_builder.py` (python-docx generation)
6. `cover_letter/generator.py` (LangChain cover letter drafting)
7. Spanish support: `ats_resume_es.tex.j2`, language toggle in config
8. Update CLI: `tycho dashboard` (Rich interactive browser), scoring display, batch operations
9. Update `collect` to auto-score on collection

**Deliverable**: Full pipeline — collect → auto-score → review dashboard → generate tailored CV (.docx + .pdf) + cover letter with LLM personalization.

**Additional dependencies**: `langchain`, `langchain-anthropic`, `langchain-openai`, `python-docx`

### Phase 3 — Full Version
**Goal**: Web dashboard, scheduling, analytics, polish.

**Build**:
1. FastAPI web server with HTMX frontend
2. Job browsing dashboard (filter, sort, bulk actions)
3. Side-by-side job description + generated materials preview
4. Scheduling via APScheduler (daily/weekly auto-collection)
5. Application analytics (response rates, score accuracy tracking)
6. Feedback loop: adjust scoring weights based on which jobs user marks "interested"
7. Email/notification support for new high-scoring jobs
8. Alembic for DB migrations
9. Advanced matching: embedding-based semantic similarity (Phase 3 stretch)

**Additional dependencies**: `fastapi`, `uvicorn`, `htmx`, `apscheduler`, `alembic`

---

## Verification Plan

### Phase 1 Testing
- `tycho profile` validates all profile YAML files load without errors
- `tycho collect` returns jobs and stores them in SQLite
- `tycho jobs` displays a formatted table of collected jobs
- `tycho generate <id>` produces a PDF that:
  - Opens correctly
  - Contains tailored content (different bullets for different jobs)
  - Passes copy-paste test (select all text → paste in notepad → readable)
  - Passes Jobscan ATS check (free tier)
- Unit tests for: normalization, dedup, module selection, multi-file YAML loading

### Phase 2 Testing
- Cover letter is coherent and references the specific job
- .docx opens in Word/Google Docs with correct formatting
- Scoring ranks clearly relevant jobs higher than irrelevant ones
- LLM module selection picks different bullets for ML vs backend roles
- Dashboard is navigable and responsive

### Phase 3 Testing
- Web dashboard loads and displays jobs
- Scheduling runs on time and deduplicates across runs
- Analytics display meaningful charts
- End-to-end: schedule → collect → score → notify → review → generate → track

---

## Critical Files to Modify/Create First (Phase 1)

1. `pyproject.toml` — project setup
2. `config.yaml` — user configuration
3. `profile/personal.yaml`, `profile/skills.yaml`, `profile/experience/*.yaml`, `profile/education/*.yaml` — curated from existing CVs
4. `profile/templates/ats_resume.tex.j2` — ATS-friendly LaTeX template
5. `src/tycho/models.py` — all Pydantic models
6. `src/tycho/db.py` — database setup
7. `src/tycho/collector/jobspy_collector.py` — JobSpy integration
8. `src/tycho/cv/profile_loader.py` — YAML loading
9. `src/tycho/cv/module_selector.py` — tag-based selection
10. `src/tycho/cv/latex_builder.py` — PDF generation
11. `src/tycho/cli.py` — Typer commands
