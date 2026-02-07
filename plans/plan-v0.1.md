# Job Application Automation System - Architecture Plan

## Overview
A Python-based system to automate job searching, CV personalization, and application management with both CLI and web interfaces.

## Key Requirements (from discussion)
- **Language**: Python
- **Interface**: CLI + Web dashboard
- **Data Sources**: Hybrid (APIs + aggregators + selective scraping)
- **Automation Level**: Semi-automatic (auto-apply high matches, review others)
- **Hosting**: Local-first, deployable later
- **LLM**: Multi-provider support (OpenAI, Anthropic, Ollama)
- **Storage**: SQLite (jobs/history) + JSON/YAML (configs, CV data)
- **Target Roles**: Software/Tech + General professional
- **Job Boards**: Standard (Indeed, LinkedIn, Glassdoor, Adzuna) + Tech-specific (Greenhouse, AngelList, BuiltIn) + Remote-focused (Remotive, We Work Remotely)
- **Existing CV**: LaTeX format (can export to PDF, or start fresh with YAML)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interfaces                          │
├─────────────────────────────────────────────────────────────────┤
│     CLI (typer/click)          │      Web Dashboard (FastAPI)   │
│     - Run collections          │      - Browse/filter jobs      │
│     - Generate docs            │      - Review applications     │
│     - Quick status             │      - Edit CV/letters         │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                         Core Engine                             │
├─────────────────────────────────────────────────────────────────┤
│  Job Collector  │  CV Engine  │  Cover Letter  │  Applicator   │
│  - Adapters     │  - Parser   │  Generator     │  - Matcher    │
│  - Normalizer   │  - Builder  │  - Templates   │  - Submitter  │
│  - Deduper      │  - Exporter │  - LLM calls   │  - Tracker    │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                      Infrastructure                             │
├─────────────────────────────────────────────────────────────────┤
│  LLM Provider   │   Storage Layer   │   Scheduler (APScheduler) │
│  Abstraction    │   SQLite + Files  │   or cron                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Job Collection System

**Adapters (plugin architecture)**:
```
/collectors
  /base.py              # Abstract adapter interface
  # Standard
  /indeed.py            # Indeed via RapidAPI/JSearch
  /linkedin.py          # LinkedIn (limited - RSS or manual import)
  /glassdoor.py         # Glassdoor via aggregator APIs
  /adzuna.py            # Adzuna API (free tier available)
  # Remote-focused
  /remotive.py          # Remotive API (remote jobs)
  /weworkremotely.py    # We Work Remotely RSS feed
  /remoteok.py          # Remote OK API
  # Tech-specific
  /greenhouse.py        # Greenhouse job boards
  /lever.py             # Lever job boards
  /angellist.py         # AngelList/Wellfound
  /builtin.py           # BuiltIn city boards
```

**Data flow**:
1. Scheduler triggers collection (daily/weekly)
2. Each adapter fetches jobs → normalized Job objects
3. Deduplication by (company, title, location) hash
4. Store in SQLite with status='new'

**Job Schema**:
```python
class Job:
    id: str                  # UUID
    external_id: str         # Source's ID
    source: str              # 'indeed', 'linkedin', etc.
    title: str
    company: str
    location: str
    remote: bool
    description: str
    requirements: list[str]  # Extracted
    salary_min: int | None
    salary_max: int | None
    url: str
    posted_date: datetime
    collected_date: datetime
    status: str              # 'new', 'reviewing', 'applied', 'rejected', 'ignored'
    match_score: float       # 0-1, computed by matcher
```

### 2. CV Personalization Engine

**Import Options**:
- **From LaTeX**: Parse `.tex` file to extract sections (experience, education, skills). Since LaTeX is structured, we can use regex or a simple parser to pull data into the YAML schema.
- **From scratch**: Manually populate `master_cv.yaml`
- **Hybrid**: Use LLM to help convert LaTeX → YAML structure

**Master CV Structure** (`cv_data/master_cv.yaml`):
```yaml
personal:
  name: "Your Name"
  email: "email@example.com"
  phone: "+1-xxx-xxx-xxxx"
  location: "City, Country"
  linkedin: "linkedin.com/in/..."
  github: "github.com/..."

summary:
  default: "Experienced software engineer..."
  variations:
    backend: "Backend-focused engineer..."
    fullstack: "Full-stack developer..."
    data: "Data-oriented engineer..."

experience:
  - company: "Company A"
    title: "Senior Engineer"
    dates: "2020-Present"
    bullets:
      - text: "Led migration to microservices"
        tags: [backend, architecture, leadership]
        extended: "Detailed version with metrics..."
      - text: "Reduced API latency by 40%"
        tags: [backend, performance, python]

skills:
  languages: [Python, TypeScript, Go]
  frameworks: [FastAPI, React, Django]
  # ... categorized skills

keywords_map:
  "machine learning": [tensorflow, pytorch, ml]
  "cloud": [aws, gcp, kubernetes]
```

**CV Generation Pipeline**:
1. Parse job description → extract keywords
2. Match keywords to CV sections/bullets
3. Select relevant bullets (tag matching + LLM ranking)
4. Generate tailored summary (LLM)
5. Build CV document
6. Export to PDF (weasyprint) or DOCX (python-docx)

### 3. Cover Letter Generator

**Template System** (`templates/cover_letters/`):
```yaml
# default.yaml
structure:
  - opening: "greeting + hook"
  - why_company: "research-based paragraph"
  - why_me: "relevant experience highlights"
  - closing: "call to action"

tone: professional
max_length: 400  # words
```

**Generation Flow**:
1. Fetch job + company info
2. Select relevant CV bullets
3. LLM generates draft following template structure
4. Store for review/editing

### 4. Job Matcher & Scorer

**Scoring Factors**:
- Keyword match (job requirements vs CV skills): 40%
- Title relevance: 20%
- Location/remote preference: 15%
- Salary range fit: 15%
- Company size/type preference: 10%

**Thresholds** (`config.yaml`):
```yaml
matching:
  auto_apply_threshold: 0.85  # Auto-apply if score >= this
  review_threshold: 0.50      # Show in review queue if >= this
  ignore_threshold: 0.30      # Auto-ignore if < this
```

### 5. Application Submitter

**Strategies by source**:
- **Easy Apply (LinkedIn)**: Browser automation (Playwright) - risky, may violate ToS
- **Greenhouse/Lever**: API-based where available
- **Email applications**: Generate email with attachments
- **Manual queue**: Generate materials, user applies manually

**Recommended approach**: Focus on material generation (CV + cover letter), provide "Apply" links, let user do final submission for most platforms.

### 6. Web Dashboard (FastAPI + HTMX or React)

**Pages**:
- `/jobs` - Browse collected jobs, filter by status/score/source
- `/jobs/{id}` - Job detail, generated CV preview, apply actions
- `/applications` - Track application history
- `/cv` - View/edit master CV data
- `/settings` - Configure sources, thresholds, LLM provider

### 7. CLI Interface

```bash
# Collection
tycho collect --source all          # Run all adapters
tycho collect --source indeed       # Single source

# Review
tycho jobs list --status new --min-score 0.7
tycho jobs show <job-id>

# Generation
tycho generate cv <job-id> --output pdf
tycho generate letter <job-id>

# Application
tycho apply <job-id>                # Mark as applied, open URL
tycho apply --auto                  # Apply to all above threshold

# Status
tycho status                        # Summary stats
```

---

## Project Structure

```
tycho/
├── pyproject.toml
├── config.yaml                 # User configuration
├── cv_data/
│   ├── master_cv.yaml         # Your full CV data
│   └── templates/             # CV format templates
├── src/
│   └── tycho/
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   └── commands.py
│       ├── web/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   └── routes/
│       ├── core/
│       │   ├── models.py      # Pydantic models
│       │   ├── database.py    # SQLite/SQLAlchemy
│       │   └── config.py      # Settings management
│       ├── collectors/
│       │   ├── base.py
│       │   ├── indeed.py
│       │   └── ...
│       ├── cv/
│       │   ├── parser.py
│       │   ├── builder.py
│       │   └── exporter.py
│       ├── letters/
│       │   └── generator.py
│       ├── matcher/
│       │   └── scorer.py
│       └── llm/
│           ├── base.py
│           ├── openai.py
│           ├── anthropic.py
│           └── ollama.py
├── templates/
│   ├── cv/
│   └── cover_letters/
└── tests/
```

---

## Key Dependencies

```toml
[project]
dependencies = [
    # Core
    "pydantic>=2.0",
    "sqlalchemy>=2.0",
    "pyyaml",

    # CLI
    "typer[all]",
    "rich",

    # Web
    "fastapi",
    "uvicorn",
    "jinja2",

    # Job collection
    "httpx",              # Async HTTP client
    "beautifulsoup4",     # HTML parsing
    "playwright",         # Browser automation (optional)

    # Document generation
    "weasyprint",         # PDF generation
    "python-docx",        # DOCX generation

    # LLM
    "openai",
    "anthropic",

    # Scheduling
    "apscheduler",
]
```

---

## Implementation Phases

### Phase 1: Foundation
- [ ] Project setup (pyproject.toml, structure)
- [ ] Core models and database schema
- [ ] Config system (Pydantic settings)
- [ ] Basic CLI skeleton

### Phase 2: Job Collection
- [ ] Base adapter interface
- [ ] 2-3 initial adapters (JSearch/Indeed, Adzuna, Remotive)
- [ ] Job normalization and deduplication
- [ ] CLI commands for collection

### Phase 3: CV Engine
- [ ] Master CV YAML schema and parser
- [ ] Keyword extraction from job descriptions
- [ ] CV builder with bullet selection
- [ ] PDF/DOCX export

### Phase 4: LLM Integration
- [ ] Provider abstraction layer
- [ ] OpenAI and Anthropic implementations
- [ ] Ollama for local models
- [ ] Cover letter generation
- [ ] CV summary customization

### Phase 5: Matching & Scoring
- [ ] Scoring algorithm
- [ ] Threshold-based categorization
- [ ] CLI commands for review

### Phase 6: Web Dashboard
- [ ] FastAPI app setup
- [ ] Job listing and detail pages
- [ ] Application tracking
- [ ] CV preview and editing

### Phase 7: Polish & Automation
- [ ] Scheduling setup
- [ ] Email notifications (optional)
- [ ] Application link generation
- [ ] Browser automation for easy-apply (optional, careful with ToS)

---

## Legal & Ethical Considerations

1. **Terms of Service**: Most job boards prohibit scraping. Use official APIs and aggregators where possible.
2. **Rate Limiting**: Respect rate limits, add delays between requests.
3. **Data Privacy**: Store your own data locally; don't scrape/store other users' data.
4. **Application Authenticity**: Auto-generated materials should still be reviewed; don't spam applications.

---

## Verification Plan

1. **Unit tests**: Test each component in isolation (collectors, CV builder, scorer)
2. **Integration test**: Run collection → scoring → CV generation pipeline
3. **Manual testing**:
   - Run `tycho collect` and verify jobs appear in DB
   - Generate CV for a specific job, verify PDF output
   - Launch web dashboard, browse jobs, trigger generation
4. **End-to-end**: Apply to a test job posting (or one you create) using generated materials

---

## Next Steps After Approval

1. Initialize project structure and `pyproject.toml`
2. Set up core models and SQLite database
3. Create config system with your preferences (locations, job titles, salary range)
4. Build first 2-3 job collectors (JSearch for Indeed, Remotive, Adzuna)
5. Create LaTeX → YAML CV importer (or help you build master CV from scratch)
6. Build CV generation pipeline with PDF export
