# Tycho — Automated Job Application Platform

Tycho collects job postings from LinkedIn and Indeed, scores them against a modular YAML profile, and generates tailored CVs (LaTeX PDF + .docx for ATS) with per-job bullet selection and focus-area detection. Includes a web dashboard (FastAPI + HTMX) and scheduled collection.

## Quick Start

```bash
uv venv && uv pip install -e ".[web]" --python .venv/bin/python
source .venv/bin/activate
tycho profile          # validate profile YAML
tycho config-cmd           # show current configuration
tycho collect          # scrape jobs from LinkedIn + Indeed + company careers pages
tycho collect --companies-only   # only configured company careers pages (skip JobSpy)
tycho jobs             # list jobs sorted by score
tycho show <id>        # inspect job + score breakdown
tycho generate <id>    # generate tailored CV
tycho mark <id> interested
tycho rescore          # re-score all jobs against current profile/config
tycho dashboard        # CLI dashboard: summary stats + top 10 (Rich TUI)
tycho serve            # Web dashboard: http://0.0.0.0:8000 (FastAPI + HTMX)
```

Job IDs support prefix matching — `tycho show abc` matches `abc12345-...`.

## Project Structure

```
tycho/
├── config.yaml                     # Search terms, scoring weights, output settings
├── pyproject.toml                  # Dependencies, build config (hatchling)
├── alembic/                        # Database migrations
│   ├── alembic.ini
│   ├── env.py                      # Imports tycho.db.Base for autogenerate
│   └── versions/                   # Migration scripts
├── profile/                        # Multi-file YAML profile (one file per entry)
│   ├── personal.yaml               # Name, contact, summary variations
│   ├── skills.yaml                 # Technical skills (tagged, prioritized) + languages
│   ├── experience/*.yaml           # One file per work experience
│   ├── education/*.yaml            # One file per education entry
│   ├── other/*.yaml                # Hackathons, leadership, etc.
│   └── templates/
│       ├── ats_resume.tex.j2       # ATS-friendly LaTeX template (English)
│       ├── ats_resume_es.tex.j2    # ATS-friendly LaTeX template (Spanish)
│       ├── developer_cv.tex.j2     # Modern developer CV template (English)
│       └── developer_cv_es.tex.j2  # Modern developer CV template (Spanish)
├── src/tycho/
│   ├── cli.py                      # Typer CLI (all commands including `serve`)
│   ├── config.py                   # Pydantic settings (WebConfig, SchedulerConfig, etc.)
│   ├── models.py                   # All Pydantic models (Job, Profile, TailoredProfile, etc.)
│   ├── db.py                       # SQLAlchemy + SQLite (Job + ScheduleRun tables, CRUD)
│   ├── collector/
│   │   ├── base.py                 # Abstract collector interface
│   │   ├── jobspy_collector.py     # python-jobspy integration (LinkedIn + Indeed)
│   │   ├── company_collector.py    # Direct ATS job board APIs (Greenhouse, Lever, Ashby, ...)
│   │   ├── parsing.py              # Shared defensive value parsing (str/float/date)
│   │   └── normalize.py            # Deduplication by (company, title, location) hash
│   ├── matcher/
│   │   ├── keywords.py             # Regex + LLM keyword extraction from job descriptions
│   │   └── scorer.py               # Weighted scoring (keyword, title, skills, location)
│   ├── cv/
│   │   ├── profile_loader.py       # Load multi-file YAML → Profile model
│   │   ├── module_selector.py      # Tag-based + LLM bullet selection + focus detection
│   │   ├── latex_builder.py        # Jinja2 render → pdflatex/latexmk compile
│   │   └── docx_builder.py         # python-docx ATS-safe generation
│   ├── cover_letter/
│   │   └── generator.py            # LLM-based cover letter drafting
│   ├── llm/
│   │   └── client.py               # LangChain multi-provider wrapper
│   ├── web/                        # FastAPI + HTMX web dashboard
│   │   ├── app.py                  # App factory + lifespan (scheduler start/stop)
│   │   ├── deps.py                 # Dependency injection (session, config, profile, llm)
│   │   ├── routes/
│   │   │   ├── jobs.py             # GET /jobs, GET /jobs/{id}, POST status, POST bulk-status
│   │   │   ├── generate.py         # GET/POST /generate/{id}, download endpoint
│   │   │   └── schedule.py         # GET /schedule, POST trigger/update, GET status
│   │   ├── templates/              # Jinja2 HTML templates (standard delimiters)
│   │   │   ├── base.html           # Layout: nav, Pico CSS, HTMX script
│   │   │   ├── jobs/               # list, _table, _row, detail
│   │   │   ├── generate/           # preview, _preview_panel
│   │   │   └── schedule/           # index, _status
│   │   └── static/                 # CSS + JS
│   └── scheduler/
│       └── scheduler.py            # APScheduler BackgroundScheduler + collection_task
├── output/                         # Generated CVs go here (gitignored)
└── tests/
    ├── test_web/                   # TestClient tests for all web routes
    └── test_scheduler.py           # Scheduler + DB helper tests
```

## Architecture

### Data Flow

```
tycho collect → JobSpy scrape + company ATS APIs → normalize/dedup → score against profile → SQLite
tycho generate <id> → load profile → detect focus → select bullets/variations → Jinja2 → LaTeX → PDF
tycho serve → FastAPI + HTMX dashboard → browse/filter/generate from browser
scheduler (optional) → APScheduler cron → collection_task → same pipeline as collect
```

### Key Design Decisions

| Decision | Choice | Notes |
|----------|--------|-------|
| Job scraping | `python-jobspy` (not `jobspy`) | Scrapes LinkedIn + Indeed concurrently |
| Jinja2 delimiters (LaTeX) | Blocks: `<% %>`, Variables: `{{ }}`, Comments: `<# #>` | `<% %>` avoids conflicts with LaTeX `{ }` |
| Jinja2 delimiters (HTML) | Standard `{% %}` / `{{ }}` | Separate Jinja2 env from LaTeX templates |
| venv install | `uv pip install -e ".[web]" --python .venv/bin/python` | Must target venv explicitly with uv |
| Profile format | Multi-file YAML, one per entry | Clean diffs, easy to add/disable entries |
| Storage | SQLite via SQLAlchemy (sync) | Local-first, single-process Pi deployment |
| CLI | Typer + Rich | `tycho` entry point defined in pyproject.toml |
| CV tailoring | Tag-based (Phase 1), LLM-based (Phase 2) | Focus detection: ml_focus, backend_focus, data_focus |
| LLM abstraction | LangChain multi-provider | Anthropic/OpenAI/Ollama, lazy init, dynamic imports |
| Graceful degradation | `if llm_client and llm_client.available` guard | Falls back to Phase 1 behavior when no API key or `--no-llm` |
| DOCX output | python-docx, Calibri 10pt, ATS-safe | No images, native Word bullets, 0.7" margins |
| Template system | Multiple templates + language variants | `ats_resume` (ATS), `developer_cv` (modern); `_es` for Spanish |
| Web framework | FastAPI + HTMX + Pico CSS | No JS build step, ~10KB CSS, CDN-delivered |
| Scheduler | APScheduler 3.x BackgroundScheduler | Thread-based, well-tested, simple for single-process |
| Optional deps | `pip install tycho[web]`, `tycho[anthropic]`, `tycho[all-llm]` | LLM providers are optional, CLI users don't need FastAPI |

### Web Dashboard Architecture

- **Pico CSS** (classless, CDN): Clean defaults for tables/forms/buttons, no build step
- **HTMX**: Inline status changes, filtered table reloads, polling for scheduler status
- **`app.state`**: Config, engine, scheduler stored on FastAPI app state (single-process)
- **Dependency injection**: `get_db`, `get_config`, `get_templates`, `get_llm_client` via FastAPI `Depends`

| HTMX Pattern | Method | Target | Swap |
|--------------|--------|--------|------|
| Filter/paginate | GET /jobs?status=X | #job-table | innerHTML |
| Inline status | POST /jobs/{id}/status | #job-{id[:8]} | outerHTML |
| Bulk status | POST /jobs/bulk-status | #job-table | innerHTML |
| Generate CV | POST /generate/{id} | #preview-panel | innerHTML |
| Schedule poll | GET /schedule/status | #status-panel | innerHTML (every 30s) |

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

### Company Careers Page Monitoring (company_collector.py)

Monitors specific companies' careers pages directly via their ATS provider's public JSON API — no HTML scraping, independent of LinkedIn/Indeed. Configured under `companies:` in config.yaml (name + URL is enough); provider and board slug are auto-detected from the URL, with `provider:`/`board:` overrides for unusual setups and `enabled: false` to pause a company.

- **Supported providers:** greenhouse, lever, ashby, workable, smartrecruiters, recruitee, personio
- **Registry pattern:** `PROVIDERS` dict maps name → `Provider(url_patterns, fetch)`. Adding a new ATS = one entry: URL regex(es) with the board slug as first capture group + a fetch function mapping the API's JSON to `Job`
- **Job mapping:** `source` = provider name, `source_id` = ATS job id (satisfies the `(source, source_id)` upsert constraint), `company` = the configured display name (keeps dedup keys stable)
- **Everything is collected** (no term filtering) — company boards are small and the scorer ranks the postings
- **Compensation:** adapters map pay ranges into `salary_min/max/currency/interval` where the ATS exposes them
- **Error isolation:** one failing/unrecognized company prints a `[warning]` and never aborts the run
- Runs as part of `tycho collect` and scheduled collection; `--companies-only` skips JobSpy, `--no-companies` skips company boards

### Scoring Algorithm (scorer.py)

Score = weighted sum of 4 components (weights in config.yaml):

- **keyword_match** (0.30): % of job description keywords found in profile skills, scaled by extraction confidence (`scoring.min_keywords_confidence`, must be >= 1: keyword count needed for full confidence)
- **title_match** (0.20): Profile-recall — fraction of profile title words (minus seniority stopwords) found in the job title
- **skills_overlap** (0.35): Profile recall — fraction of your core (priority-1) skills the job mentions
- **location_match** (0.15): Binary — 1.0 for remote/known cities, 0.0 otherwise. Uses word-boundary regex to avoid false positives. Locations are configurable via `scoring.locations` in config.yaml. Abbreviations (e.g. `es` → `spain`) are expanded before matching.

The weighted sum is then multiplied by a **recency factor** (`scoring.recency` in config.yaml): 1.0 up to `full_score_days`, decaying linearly to `min_factor` at `decay_days`, so stale postings sink in the ranking. Age comes from `date_posted` (falling back to `date_collected`; unknown age = no penalty). The factor and age are recorded in `score_details` (`recency_factor`, `age_days`). Note: stored scores only decay when re-scored — `tycho collect` refreshes re-seen Indeed/company jobs but skips LinkedIn jobs already stored with a description (see below), so run `tycho rescore` periodically.

Collection skips known LinkedIn jobs: it scrapes LinkedIn cards without descriptions and fetches a description only for jobs not already in the DB with a non-empty description (via jobspy's private `LinkedIn._get_job_details`). Jobs stored with an empty description are retried next run. Each search logs timing and the already-known share, and a per-term summary prints at the end.

Collection also enforces freshness upstream: `search.max_age_days` (code default 30; `config.yaml` uses 7 for the daily run, backfill with `tycho collect --max-age-days 30`) is passed to JobSpy as `hours_old` and stale rows are dropped defensively (LinkedIn leaks old postings past the filter). Jobs and the web dashboard show a Posted/Age column, sortable and filterable by `--max-age-days` / `max_age_days`.

### Focus Detection (module_selector.py)

When generating a CV, the selector detects the job's focus area by counting indicator keywords:

- **ml_focus**: pytorch, tensorflow, machine learning, deep learning, computer vision, etc.
- **backend_focus**: backend, api, fastapi, django, docker, kubernetes, etc.
- **data_focus**: data science, analytics, pandas, statistics, etc.

This determines which bullet variations and summary to use.

### LLM Integration (client.py)

`LLMClient` in `src/tycho/llm/client.py` wraps LangChain chat models with lazy initialization and provider abstraction.

**Methods:**
- `invoke(prompt)` → `str` — plain text response
- `invoke_structured(prompt, output_schema)` → `BaseModel` — parsed into a Pydantic model via `with_structured_output()`
- `available` property — checks: `enabled` config flag, provider package installed, API key present

**Providers:**

| Provider | LangChain Package | API Key Env Var | Install Extra |
|----------|-------------------|-----------------|---------------|
| `anthropic` | `langchain-anthropic` | `ANTHROPIC_API_KEY` | `tycho[anthropic]` |
| `openai` | `langchain-openai` | `OPENAI_API_KEY` | `tycho[openai]` |
| `ollama` | `langchain-ollama` | None (local) | `tycho[ollama]` |

Install all providers: `pip install tycho[all-llm]`

**Graceful degradation pattern:** Every LLM call site uses `if llm_client and llm_client.available`, wrapped in `try/except` with fallback to Phase 1 behavior. The `--no-llm` CLI flag skips creating the client entirely.

**LLM-enhanced features:**
- **Keyword extraction** (`matcher/keywords.py`): Hybrid regex + LLM. `extract_keywords_llm()` returns `LLMKeywordResult` (structured output with `keywords`, `required_skills`, `nice_to_have_skills`). Results are merged with regex keywords.
- **Bullet re-ranking** (`cv/module_selector.py`): `_llm_rerank_bullets()` asks the LLM to rank bullets by relevance to the job. Response is a comma-separated list of indices (e.g., `2,1,3`). Falls back to tag-based order on parse failure.
- **Focus detection fallback** (`cv/module_selector.py`): When tag-based `_detect_focus()` returns `None`, `_detect_focus_llm()` asks the LLM to classify as `ml_focus`, `backend_focus`, or `data_focus`.

### Cover Letter Generation (generator.py)

`generate_cover_letter()` in `src/tycho/cover_letter/generator.py` produces structured cover letters via LLM.

**Pipeline:**
1. Build system prompt: tone, paragraph count, language, response format markers
2. Build human prompt: job title/company/description, candidate summary/skills/top 3 experiences
3. LLM `invoke()` call with combined prompt
4. Parse response using `GREETING:` / `PARAGRAPH:` / `CLOSING:` markers → `CoverLetter` model
5. Fallback: if markers aren't found, raw text becomes a single paragraph

**Output:** `CoverLetter` model with `greeting`, `paragraphs`, `closing`, `full_text` property. Saved as `.txt` (plain text) and `.docx` (Calibri 11pt).

**Config:** `cover_letter.max_paragraphs` (default 3), `cover_letter.tone` (default "professional").

**CLI:** `tycho generate <id> --cover-letter` (or `--cl`)

### DOCX Builder (docx_builder.py)

`build_docx()` in `src/tycho/cv/docx_builder.py` generates ATS-safe Word documents from a `TailoredProfile`.

**Formatting:** Calibri 10pt, black text (#000000), gray accents (#505050 for titles, #646464 for dates/location), 0.7" margins on all sides, native Word `List Bullet` style.

**Section order:** Name (16pt bold, centered) → Titles (10pt gray) → Contact (9pt) → Summary → Skills → Experience → Education → Other → Languages

**Language support:** Section headings switch between English and Spanish (e.g., "Work Experience" / "Experiencia Laboral").

**Phone selection:** Country-aware — `country == "Spain"` uses `phone_es`, otherwise `phone_uk`.

### Template System

Two LaTeX templates are available, each with English and Spanish variants:

| Template | Class | Font | Style | File |
|----------|-------|------|-------|------|
| `ats_resume` | `article` | `lmodern` | ATS-optimized, single-column, minimal | `ats_resume.tex.j2` |
| `developer_cv` | `extarticle` | `raleway` | Modern, styled section headers | `developer_cv.tex.j2` |

**Language variants:** `{template}.tex.j2` (English), `{template}_es.tex.j2` (Spanish). Selected automatically based on `--lang` flag.

**Selection:** `--template` / `-t` CLI flag or `output.template` config key. Default: `ats_resume`.

All templates use the same Jinja2 custom delimiters (`<% %>` for blocks, `{{ }}` for variables).

### Database (db.py)

Two tables:
- **jobs**: Unique constraint on `(source, source_id)` for dedup. Status flow: new → reviewed → interested → applied → rejected → archived
- **schedule_runs**: Tracks automated collection runs (timestamp, counts, status, errors)

Key DB helpers:
- `get_jobs_paginated()`: Offset/limit pagination with filtering and search
- `get_job_by_prefix()`: Consolidates prefix matching logic
- `get_schedule_runs()`, `add_schedule_run()`: Schedule run tracking

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
  country: "Ireland"                                    # Affects phone number + default Indeed locale
  location_countries:                                   # Per-location Indeed locale overrides
    Galway: "Ireland"
    London: "UK"
  linkedin_fetch_description: true                      # Fetch full LinkedIn descriptions (slower; needed for scoring)
  results_per_source: 50                                # Per (term, location) pair
  max_age_days: 7                                       # Skip postings older than this (0/null disables); 30 for a manual backfill

companies:                       # Company careers pages monitored via ATS APIs
  - name: Acme                   # Display name (used as Job.company)
    url: https://boards.greenhouse.io/acme   # Provider + board auto-detected
  - name: Globex
    url: https://globex.example.com/jobs
    provider: lever              # Optional: override auto-detection
    board: globex                # Optional: override board slug
    enabled: true                # Optional: false to pause

scoring:
  weights:                    # Must sum to 1.0
    keyword_match: 0.35
    title_match: 0.25
    skills_overlap: 0.25
    location_match: 0.15
  thresholds:
    high_interest: 0.75       # Green highlight in dashboard
    low_interest: 0.30        # Dimmed in display
  recency:                     # Old postings decay so stale jobs sink in the ranking
    enabled: true
    full_score_days: 14        # No penalty up to this age
    decay_days: 90             # Linear decay ends here
    min_factor: 0.4            # Score multiplier floor
  locations:
    preferred:                 # English location names (word-boundary matched)
      - madrid
      - london
      - edinburgh
      - spain
      - uk
    preferred_es:              # Spanish location names
      - españa
      - reino unido
      - edimburgo
      - londres
    remote_keywords:           # Always score 1.0
      - remote
      - remoto
    abbreviations:             # Short codes expanded before matching
      md: madrid
      es: spain
      gb: united kingdom

llm:
  provider: "anthropic"       # anthropic, openai, ollama
  model: "claude-sonnet-4-5-20250929"
  temperature: 0.3
  enabled: true
  base_url: null              # Optional: for Ollama or self-hosted endpoints

cover_letter:
  max_paragraphs: 3
  tone: "professional"

output:
  formats: ["pdf", "docx"]   # pdf, tex, docx
  language: "en"              # en, es
  template: "ats_resume"     # ats_resume, developer_cv

web:
  host: "0.0.0.0"             # Bind host
  port: 8000                  # Bind port
  reload: false               # Auto-reload for development

scheduler:
  enabled: false              # Set true to enable automated collection
  cron: "0 8 * * *"          # Cron expression (daily at 8 AM)

profile_dir: "profile"
db_path: "tycho.db"
output_dir: "output"
```

## Development Workflow

The main checkout is the **live pipeline**: the daily collect (hive worker in `tycho-worker/`) runs the globally installed `tycho`, whose editable install points at this checkout's `src/`, and `config.yaml`, `tycho.db` and `profile/` live here too. Changing branches or files here changes what production runs.

- Keep the main checkout on `main`, with a clean tree. Pull merged changes with `git merge --ff-only origin/main`.
- Do all feature work and PR fixes in a worktree: `git worktree add .worktrees/<name> -b <branch> main` (`.worktrees/` is gitignored). Run tests there with `PYTHONPATH=<worktree>/src .venv/bin/python -m pytest`.
- Never use bare `git stash`, `git checkout <branch>` or `git reset` in the main checkout, and don't run several Claude sessions against it at once.
- Known local-only edit: the macOS texlive path in `extra_paths` in `src/tycho/cv/latex_builder.py` stays uncommitted. Re-apply it after any change that touches that file.

## Phase Status

- **Phase 1 (PoC)**: COMPLETE — collect, score, browse, generate tailored CVs
- **Phase 2 (MVP)**: COMPLETE — LLM integration (LangChain), .docx output, cover letters, LLM keyword extraction, bullet re-ranking
- **Phase 3 (Full)**: COMPLETE — FastAPI + HTMX web dashboard, APScheduler, Alembic migrations

## Common Tasks

**Add a new experience entry:**
Create `profile/experience/new_job.yaml` following the schema above. Run `tycho profile` to validate.

**Monitor a company's careers page:**
Add `- name: Acme` / `url: https://boards.greenhouse.io/acme` under `companies:` in config.yaml. Provider is auto-detected. Collect with `tycho collect` (or `--companies-only`).

**Change search terms:**
Edit `config.yaml` → `search.terms` and `search.locations`.

**Adjust scoring:**
Edit `config.yaml` → `scoring.weights` (must sum to 1.0).

**Customize location matching:**
Edit `config.yaml` → `scoring.locations` to add preferred cities, abbreviations, or remote keywords.

**Re-score all jobs after config/profile changes:**
`tycho rescore`

**View current configuration:**
`tycho config-cmd`

**View CLI dashboard (Rich TUI with stats):**
`tycho dashboard`

**Generate Spanish CV:**
`tycho generate <id> --lang es`

**Generate just the .tex source (no PDF compilation):**
`tycho generate <id> --format tex`

**Generate DOCX only:**
`tycho generate <id> --format docx`

**Generate CV with cover letter:**
`tycho generate <id> --cover-letter`

**Generate without LLM (Phase 1 behavior):**
`tycho generate <id> --no-llm`

**Use developer CV template:**
`tycho generate <id> --template developer_cv`

**Install with specific LLM provider:**
`pip install tycho[anthropic]` or `pip install tycho[all-llm]`

**Start web dashboard:**
`tycho serve` (default: http://0.0.0.0:8000)

**Start with auto-reload (development):**
`tycho serve --reload`

**Enable automated collection:**
Set `scheduler.enabled: true` and `scheduler.cron: "0 8 * * *"` in config.yaml, then `tycho serve`.

**Install for Raspberry Pi deployment:**
`pip install tycho[web] && tycho serve --host 0.0.0.0`
