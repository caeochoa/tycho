# Tycho

Automated job application platform that scrapes job postings, scores them against your profile, and generates tailored CVs.

## Features

- **Job collection** from LinkedIn and Indeed via [python-jobspy](https://github.com/Bunsly/JobSpy)
- **Weighted scoring** against a modular YAML profile (keyword match, title similarity, skills overlap, location)
- **Tailored CV generation** with per-job bullet selection and focus-area detection (ML, backend, data)
- **Multiple output formats** — LaTeX PDF, .docx (ATS-safe), and raw .tex
- **Bilingual support** — English and Spanish templates, section headings, and bullet variations
- **LLM integration** (optional) — enhanced keyword extraction, bullet re-ranking, cover letter generation
- **Web dashboard** — FastAPI + HTMX + Pico CSS for browsing, filtering, and generating from the browser
- **Telegram bot** — remote job management from your phone
- **Scheduled collection** — APScheduler cron for hands-off daily scrapes
- **CLI** — Rich-powered terminal interface with dashboard, tables, and score breakdowns

## Quick Start

```bash
# Create venv and install
uv venv
uv pip install -e ".[web]" --python .venv/bin/python
source .venv/bin/activate

# Set up your profile
# Edit YAML files in profile/ (see Profile System below)
tycho profile          # validate profile

# Configure search terms and scoring
# Edit config.yaml (see Configuration below)

# Collect and browse jobs
tycho collect          # scrape from LinkedIn + Indeed
tycho jobs             # list jobs sorted by score
tycho show <id>        # inspect a job + score breakdown

# Generate a tailored CV
tycho generate <id>    # PDF + DOCX by default
```

Requires Python 3.11+. PDF output requires `pdflatex` or `latexmk`.

## CLI Commands

| Command | Description |
|---------|-------------|
| `tycho collect` | Scrape jobs from LinkedIn and Indeed |
| `tycho jobs` | List collected jobs (filterable by status, score) |
| `tycho show <id>` | Show job details and score breakdown |
| `tycho generate <id>` | Generate a tailored CV for a job |
| `tycho mark <id> <status>` | Set job status (interested, applied, rejected, archived) |
| `tycho rescore` | Re-score all jobs against current profile/config |
| `tycho profile` | Validate profile YAML modules |
| `tycho dashboard` | Rich TUI with summary stats and top 10 jobs |
| `tycho config-cmd` | Display current configuration |
| `tycho serve` | Start the web dashboard (FastAPI + HTMX) |

Job IDs support prefix matching — `tycho show abc` matches `abc12345-...`.

## Configuration

All settings live in `config.yaml`:

```yaml
search:
  terms: ["AI Engineer", "Machine Learning Engineer"]
  locations: ["Remote", "Madrid", "London"]
  country: "Spain"
  results_per_source: 50

scoring:
  weights:                    # Must sum to 1.0
    keyword_match: 0.35
    title_match: 0.25
    skills_overlap: 0.25
    location_match: 0.15
  locations:
    preferred: [madrid, london, edinburgh]
    remote_keywords: [remote, remoto]
    abbreviations: { es: spain, gb: united kingdom }

llm:
  provider: "anthropic"       # anthropic, openai, ollama
  model: "claude-sonnet-4-5-20250929"
  enabled: true

output:
  formats: ["pdf", "docx"]
  language: "en"              # en, es
  template: "ats_resume"     # ats_resume, developer_cv

scheduler:
  enabled: false
  cron: "0 8 * * *"          # Daily at 8 AM

telegram:
  enabled: false
  token: ""                   # Or set TYCHO_TELEGRAM_TOKEN env var
  allowed_users: []
```

## Profile System

Your profile is a collection of YAML files in the `profile/` directory:

```
profile/
├── personal.yaml         # Name, contact, summary variations
├── skills.yaml           # Technical skills (tagged) + languages
├── experience/           # One file per work experience
│   ├── current_job.yaml
│   └── previous_job.yaml
├── education/            # One file per education entry
│   └── masters.yaml
├── other/                # Hackathons, leadership, etc.
│   └── hackathon.yaml
└── templates/            # LaTeX Jinja2 templates
```

Each experience entry is self-contained:

```yaml
id: "company_role"
type: "experience"
company: "Acme Corp"
title: "ML Engineer"
title_es: "Ingeniero de ML"        # Spanish translation
dates: "2023 - Present"
priority: 1                         # Lower = more important
tags: ["ml", "python", "pytorch"]   # Used for job matching
bullets:
  - id: "bullet_rag"
    text: "Built a RAG pipeline serving 10K queries/day"
    text_es: "Construyo un pipeline RAG..."
    tags: ["rag", "llm"]
    priority: 1
    variations:
      ml_focus: "Architected RAG pipeline with custom embeddings..."
      backend_focus: "Built production API serving 10K queries/day..."
```

- **Add an entry**: drop a `.yaml` file in the appropriate directory
- **Disable an entry**: set `enabled: false` in the YAML
- **Validate**: run `tycho profile`

## CV Generation

```bash
tycho generate <id>                    # Default: PDF + DOCX
tycho generate <id> --format pdf       # PDF only
tycho generate <id> --format docx      # DOCX only
tycho generate <id> --lang es          # Spanish
tycho generate <id> --template developer_cv   # Modern template
tycho generate <id> --cover-letter     # Include cover letter (requires LLM)
tycho generate <id> --no-llm           # Disable LLM features
```

**Templates:**

| Template | Style |
|----------|-------|
| `ats_resume` | ATS-optimized, single-column, `lmodern` font |
| `developer_cv` | Modern styled headers, `raleway` font |

Each template has English and Spanish variants (e.g., `ats_resume.tex.j2`, `ats_resume_es.tex.j2`).

**Focus detection** automatically selects the best bullet variations based on job keywords:
- `ml_focus` — pytorch, tensorflow, machine learning, deep learning
- `backend_focus` — backend, api, fastapi, django, docker
- `data_focus` — data science, analytics, pandas, statistics

## LLM Integration

LLM features are optional and degrade gracefully when unavailable.

```bash
# Install a provider
pip install tycho[anthropic]    # Claude
pip install tycho[openai]       # GPT
pip install tycho[ollama]       # Local models
pip install tycho[all-llm]      # All providers

# Set your API key
export ANTHROPIC_API_KEY=sk-...
```

LLM-enhanced features:
- **Keyword extraction** — hybrid regex + LLM for better job description parsing
- **Bullet re-ranking** — LLM ranks bullets by relevance to the specific job
- **Focus detection fallback** — LLM classifies job focus when keyword counting is ambiguous
- **Cover letter generation** — structured cover letters with configurable tone

Disable per-run with `--no-llm` or globally with `llm.enabled: false` in config.

## Web Dashboard

```bash
pip install tycho[web]
tycho serve                    # http://0.0.0.0:8000
tycho serve --reload           # Auto-reload for development
tycho serve --port 3000        # Custom port
```

Built with FastAPI + HTMX + Pico CSS (no JS build step). Provides:
- Filterable, paginated job table with inline status changes
- Job detail view with score breakdown
- CV generation and download from the browser
- Scheduler status and trigger controls

## Telegram Bot

```bash
pip install tycho[telegram]
```

Set `telegram.enabled: true` and provide a bot token (via config or `TYCHO_TELEGRAM_TOKEN` env var). The bot starts alongside the web dashboard with `tycho serve`. Restrict access with `telegram.allowed_users`.

Disable with `tycho serve --no-bot`.

## Project Structure

```
tycho/
├── config.yaml               # Search, scoring, output settings
├── profile/                  # YAML profile + LaTeX templates
├── src/tycho/
│   ├── cli.py                # Typer CLI entry point
│   ├── config.py             # Pydantic configuration models
│   ├── models.py             # Core data models (Job, Profile, etc.)
│   ├── db.py                 # SQLAlchemy + SQLite
│   ├── collector/            # Job scraping + deduplication
│   ├── matcher/              # Keyword extraction + scoring
│   ├── cv/                   # Profile loading, module selection, PDF/DOCX builders
│   ├── cover_letter/         # LLM cover letter generation
│   ├── llm/                  # LangChain multi-provider wrapper
│   ├── web/                  # FastAPI + HTMX dashboard
│   ├── telegram/             # Telegram bot handlers
│   └── scheduler/            # APScheduler background tasks
├── alembic/                  # Database migrations
├── tests/                    # 379 tests
└── output/                   # Generated CVs (gitignored)
```

## Development

```bash
# Install with all extras
uv pip install -e ".[web,all-llm,telegram]" --python .venv/bin/python

# Run tests
pytest

# Run a specific test file
pytest tests/test_scorer.py

# Run with coverage
pytest --cov=tycho
```

## License

MIT License - see [LICENSE](LICENSE) for details.
