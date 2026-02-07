# Tycho — Automated Job Application Platform

Tycho collects job postings from LinkedIn and Indeed, scores them against a modular YAML profile, and generates tailored CVs (LaTeX PDF + .docx for ATS) with per-job bullet selection and focus-area detection.

## Quick Start

```bash
uv venv && uv pip install -e . --python .venv/bin/python
source .venv/bin/activate
tycho profile          # validate profile YAML
tycho collect          # scrape jobs from LinkedIn + Indeed
tycho jobs             # list jobs sorted by score
tycho show <id>        # inspect job + score breakdown
tycho generate <id>    # generate tailored CV
tycho mark <id> interested
tycho dashboard        # summary stats + top 10
```

Job IDs support prefix matching — `tycho show abc` matches `abc12345-...`.

## Project Structure

```
tycho/
├── config.yaml                     # Search terms, scoring weights, output settings
├── pyproject.toml                  # Dependencies, build config (hatchling)
├── profile/                        # Multi-file YAML profile (one file per entry)
│   ├── personal.yaml               # Name, contact, summary variations
│   ├── skills.yaml                 # Technical skills (tagged, prioritized) + languages
│   ├── experience/*.yaml           # One file per work experience
│   ├── education/*.yaml            # One file per education entry
│   ├── other/*.yaml                # Hackathons, leadership, etc.
│   └── templates/
│       ├── ats_resume.tex.j2       # ATS-friendly LaTeX template (English)
│       └── ats_resume_es.tex.j2    # ATS-friendly LaTeX template (Spanish)
├── src/tycho/
│   ├── cli.py                      # Typer CLI (all commands)
│   ├── config.py                   # Pydantic settings loader from config.yaml
│   ├── models.py                   # All Pydantic models (Job, Profile, TailoredProfile, etc.)
│   ├── db.py                       # SQLAlchemy + SQLite (Job table, CRUD)
│   ├── collector/
│   │   ├── base.py                 # Abstract collector interface
│   │   ├── jobspy_collector.py     # python-jobspy integration (LinkedIn + Indeed)
│   │   └── normalize.py            # Deduplication by (company, title, location) hash
│   ├── matcher/
│   │   ├── keywords.py             # Regex keyword extraction from job descriptions
│   │   └── scorer.py               # Weighted scoring (keyword, title, skills, location)
│   ├── cv/
│   │   ├── profile_loader.py       # Load multi-file YAML → Profile model
│   │   ├── module_selector.py      # Tag-based bullet selection + focus detection
│   │   └── latex_builder.py        # Jinja2 render → pdflatex/latexmk compile
│   ├── cover_letter/               # Phase 2 (stub)
│   └── llm/                        # Phase 2 (stub)
├── output/                         # Generated CVs go here (gitignored)
└── tests/
```

## Architecture

### Data Flow

```
tycho collect → JobSpy scrape → normalize/dedup → score against profile → SQLite
tycho generate <id> → load profile → detect focus → select bullets/variations → Jinja2 → LaTeX → PDF
```

### Key Design Decisions

| Decision | Choice | Notes |
|----------|--------|-------|
| Job scraping | `python-jobspy` (not `jobspy`) | Scrapes LinkedIn + Indeed concurrently |
| Jinja2 delimiters | Blocks: `<% %>`, Variables: `{{ }}`, Comments: `<# #>` | `<% %>` avoids conflicts with LaTeX `{ }` |
| venv install | `uv pip install -e . --python .venv/bin/python` | Must target venv explicitly with uv |
| Profile format | Multi-file YAML, one per entry | Clean diffs, easy to add/disable entries |
| Storage | SQLite via SQLAlchemy | Local-first, zero infrastructure |
| CLI | Typer + Rich | `tycho` entry point defined in pyproject.toml |
| CV tailoring | Tag-based (Phase 1), LLM-based (Phase 2) | Focus detection: ml_focus, backend_focus, data_focus |

### Profile Module System

Each YAML file in `profile/experience/`, `profile/education/`, `profile/other/` is self-contained:

```yaml
id: "oesia_ai_engineer"
type: "experience"
company: "Grupo Oesía"
title: "AI Engineer"
title_es: "Ingeniero de IA"          # Spanish translations
dates: "2024 - Present"
priority: 1                           # Lower = more important
tags: ["ai", "ml", "python", "rag"]   # Used for job matching
skills: ["Python", "LangChain"]       # Displayed on CV
bullets:
  - id: "oesia_rag"
    text: "Led backend development of OKM..."
    text_es: "Desarrollo del backend..."     # Spanish version
    tags: ["rag", "llm", "python"]           # For relevance scoring
    priority: 1
    variations:                              # Focus-specific rewrites
      ml_focus: "Architected RAG pipeline..."
      backend_focus: "Built full-stack no-code platform..."
```

- Add a new entry: drop a `.yaml` file in the appropriate directory
- Disable an entry: set `enabled: false` in the YAML
- Bullets are scored by tag overlap with job keywords, then the best variation is selected

### Scoring Algorithm (scorer.py)

Score = weighted sum of 4 components (weights in config.yaml):

- **keyword_match** (0.35): % of job description keywords found in profile skills
- **title_match** (0.25): Jaccard similarity of job title words vs profile titles
- **skills_overlap** (0.25): Jaccard similarity of job skills vs profile skills
- **location_match** (0.15): Binary — 1.0 for remote/known cities, 0.0 otherwise

Supports Spanish location names (`remoto`, `españa`, etc.).

### Focus Detection (module_selector.py)

When generating a CV, the selector detects the job's focus area by counting indicator keywords:

- **ml_focus**: pytorch, tensorflow, machine learning, deep learning, computer vision, etc.
- **backend_focus**: backend, api, fastapi, django, docker, kubernetes, etc.
- **data_focus**: data science, analytics, pandas, statistics, etc.

This determines which bullet variations and summary to use.

### Database (db.py)

Single `jobs` table with unique constraint on `(source, source_id)` for dedup. Key fields:

- `status`: new → reviewed → interested → applied → rejected → archived
- `score` + `score_details` (JSON): match scoring results
- `cv_path` / `cover_letter_path`: generated file locations
- `tags`: JSON array of extracted keywords

### LaTeX Templates

Templates use Jinja2 with custom delimiters to avoid LaTeX conflicts:
- Blocks: `<% for x in items %>...<% endfor %>`
- Variables: `{{ x.name }}` (unchanged — no conflict with LaTeX)
- Comments: `<# this is a comment #>`

The templates are ATS-friendly: `article` class, `lmodern` font, single-column, `\pdfgentounicode=1`, no images/icons, standard `\section` headings.

PDF compilation requires `pdflatex` or `latexmk`. Falls back to `.tex` output if neither is installed.

## Config Reference (config.yaml)

```yaml
search:
  terms: ["AI Engineer", "Machine Learning Engineer"]  # JobSpy search queries
  locations: ["Remote", "Madrid", "London"]            # Search locations
  country: "Spain"                                      # Affects phone number + Indeed locale
  results_per_source: 50                                # Per (term, location) pair

scoring:
  weights:                    # Must sum to 1.0
    keyword_match: 0.35
    title_match: 0.25
    skills_overlap: 0.25
    location_match: 0.15
  thresholds:
    high_interest: 0.75       # Green highlight in dashboard
    low_interest: 0.30        # Dimmed in display

output:
  formats: ["pdf"]            # pdf, tex (Phase 2: docx)
  language: "en"              # en, es

profile_dir: "profile"
db_path: "tycho.db"
output_dir: "output"
```

## Phase Status

- **Phase 1 (PoC)**: COMPLETE — collect, score, browse, generate tailored CVs
- **Phase 2 (MVP)**: Not started — LLM integration (LangChain), .docx output, cover letters, LLM re-ranking of bullets
- **Phase 3 (Full)**: Not started — FastAPI web dashboard, scheduling, analytics, Alembic migrations

### Phase 2 Stubs

`src/tycho/llm/` and `src/tycho/cover_letter/` exist as empty packages. Phase 2 will add:
- `llm/client.py` — LangChain multi-provider wrapper (Anthropic, OpenAI, Ollama)
- `cover_letter/generator.py` — LLM-based cover letter drafting
- `cv/docx_builder.py` — python-docx generation
- LLM keyword extraction in `matcher/keywords.py`
- LLM bullet re-ranking in `cv/module_selector.py`

## Common Tasks

**Add a new experience entry:**
Create `profile/experience/new_job.yaml` following the schema above. Run `tycho profile` to validate.

**Change search terms:**
Edit `config.yaml` → `search.terms` and `search.locations`.

**Adjust scoring:**
Edit `config.yaml` → `scoring.weights` (must sum to 1.0).

**Generate Spanish CV:**
`tycho generate <id> --lang es`

**Generate just the .tex source (no PDF compilation):**
`tycho generate <id> --format tex`
