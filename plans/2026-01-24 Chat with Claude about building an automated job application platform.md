# Chat with Claude about building an automated job application platform

I’m thinking about building a solution to help me automate the search for jobs and does the following:
1. Gets job postings every day/week/month from portals like GlassDoor, Indeed, LinkedIn, etc. in the areas I’m interested in
2. Personalizes my CV to adapt it to each role, using predefined variations, extended info about my background and maybe LLMs
3. Applies to the roles, either automatically or allowing me to select the ones I’m interested in from the results obtained
4. Uses LLMs to write draft cover letters

---

This is a solid project idea, César. Given your background with RAG systems and LLM applications, you’re well-positioned to build something like this. Let me break down the key considerations for each component:

## 1\. Job Aggregation

**The challenge:** Most job portals explicitly prohibit scraping in their ToS, and they actively block automated access.

**Practical approaches:**

- **LinkedIn** has a Jobs API but it’s restricted to partners. However, LinkedIn job alerts via email could be parsed
- **Indeed** has a Publisher API (requires approval) or you could use RSS feeds for saved searches
- **Glassdoor** has a limited API for partners
- **Alternative sources:** Many companies post to their own ATS (Greenhouse, Lever, Workday) which sometimes have public APIs, or aggregate sites like RemoteOK, Otta, or Welcome to the Jungle that are more scraping-friendly
- **Email aggregation:** Set up job alerts on multiple platforms and parse the incoming emails—this sidesteps ToS issues entirely

## 2\. CV Personalization

This is where it gets interesting. A few approaches:

- **Modular CV structure:** Store your experience as atomic units (projects, skills, achievements) in a structured format (JSON/YAML), then assemble based on job requirements
- **RAG-based matching:** Embed your experience chunks and the job description, retrieve the most relevant experiences to emphasize
- **Template variations:** Pre-written variations of bullet points (technical vs business-focused language)

## 3\. Application Workflow

I’d strongly recommend **semi-automated** rather than fully automatic:

- Mass auto-applying often gets flagged or filtered
- Many applications require portal-specific questions
- Quality over quantity tends to win

A good workflow: aggregate → rank/filter → review → one-click apply with generated materials.

## 4\. Cover Letter Generation

Straightforward LLM task. Key inputs: job description, selected CV sections, company research, your voice/style examples.

---

**Want me to help you sketch out the architecture in more detail, or dive deeper into any specific component?** For instance, we could prototype the CV personalization logic or design the data model for your experience repository.

---

I want to think about it at a high level first - still at the explore and design phase. Can you help me sketch out the architecture?

---

Absolutely. Let me sketch out the high-level architecture for you.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Email Alerts    RSS Feeds      APIs (if available)     Manual Upload       │
│  (LinkedIn,      (Indeed,       (Greenhouse, Lever,     (interesting jobs   │
│   Indeed, etc)   Glassdoor)      company ATS)            you find)          │
└────────┬────────────────┬──────────────────┬───────────────────┬────────────┘
         │                │                  │                   │
         └────────────────┴────────┬─────────┴───────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Normalizes job postings into common schema                               │
│  • Deduplicates across sources                                              │
│  • Extracts structured data (title, company, requirements, etc.)            │
│  • Generates embeddings for semantic search                                 │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           JOB STORE                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  Structured Data              │  Vector Store                               │
│  ─────────────────            │  ────────────                               │
│  • Job metadata               │  • Job description embeddings               │
│  • Company info               │  • Requirements embeddings                  │
│  • Application status         │  • Skills/tech stack embeddings             │
│  • Source tracking            │                                             │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
┌───────────────────────┐ ┌──────────────────┐ ┌─────────────────────────────┐
│   MATCHING ENGINE     │ │  RANKING/FILTER  │ │     YOUR PROFILE STORE      │
├───────────────────────┤ ├──────────────────┤ ├─────────────────────────────┤
│ • Semantic similarity │ │ • Fit score      │ │  Experience atoms (JSON)    │
│   (your profile ↔ job)│ │ • Salary filter  │ │  ─────────────────────────  │
│ • Skills gap analysis │ │ • Location/remote│ │  • Projects                 │
│ • Experience matching │ │ • Company size   │ │  • Skills + proficiency     │
│                       │ │ • Role seniority │ │  • Achievements             │
│                       │ │ • Exclusions     │ │  • Education                │
│                       │ │                  │ │  • Multiple phrasings/tones │
│                       │ │                  │ │                             │
│                       │ │                  │ │  Embeddings of your profile │
└───────────┬───────────┘ └────────┬─────────┘ └──────────────┬──────────────┘
            │                      │                          │
            └──────────────────────┼──────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REVIEW INTERFACE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Dashboard of matched jobs (ranked by fit)                                │
│  • Quick actions: Interested / Skip / Save for later                        │
│  • View match reasoning (why this job? what's missing?)                     │
│  • Batch operations                                                         │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                         (User selects "Interested")
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      GENERATION PIPELINE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────┐      ┌─────────────────────────┐              │
│  │   CV PERSONALIZER       │      │   COVER LETTER GEN      │              │
│  ├─────────────────────────┤      ├─────────────────────────┤              │
│  │ 1. Retrieve relevant    │      │ 1. Company research     │              │
│  │    experience atoms     │      │    (web search/cache)   │              │
│  │ 2. Select best phrasing │      │ 2. Match your story to  │              │
│  │    variants per role    │      │    their needs          │              │
│  │ 3. Reorder sections     │      │ 3. Generate draft       │              │
│  │ 4. Render to PDF        │      │ 4. Style matching       │              │
│  └────────────┬────────────┘      └────────────┬────────────┘              │
│               │                                │                            │
│               └───────────────┬────────────────┘                            │
│                               ▼                                             │
│                    ┌─────────────────────┐                                  │
│                    │  OUTPUT PACKAGE     │                                  │
│                    │  • Tailored CV.pdf  │                                  │
│                    │  • Cover letter.pdf │                                  │
│                    │  • Application notes│                                  │
│                    └─────────────────────┘                                  │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Option A: Manual with assistance                                           │
│  ─────────────────────────────────                                          │
│  • Opens application page                                                   │
│  • Pre-fills where possible                                                 │
│  • You review and submit                                                    │
│                                                                             │
│  Option B: One-click apply (where supported)                                │
│  ────────────────────────────────────────────                               │
│  • LinkedIn Easy Apply                                                      │
│  • Direct email applications                                                │
│  • ATS with API access                                                      │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TRACKING & ANALYTICS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Application status (applied, interview, rejected, offer)                 │
│  • Response rate by: company type, role, CV variant, source                 │
│  • Time-to-response metrics                                                 │
│  • What's working? (feedback loop for ranking)                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions to Think About

**1\. Profile Store granularity** How atomic do you want your experience chunks? Options:

- Per role (coarse)
- Per project (medium)
- Per achievement/bullet point (fine)

Finer granularity = more flexibility but more work upfront and more complex assembly logic.

**2\. Matching strategy**

- Pure embedding similarity (simple, might miss nuance)
- LLM-as-judge scoring (more accurate, higher cost/latency)
- Hybrid: embeddings for retrieval, LLM for final ranking

**3\. Where does the LLM fit?**

- Ingestion: extracting structured data from job posts
- Matching: scoring fit, identifying gaps
- Generation: CVs and cover letters
- All of the above?

**4\. How much automation in applications?** Browser automation (Playwright/Selenium) is fragile and often blocked. I’d lean toward:

- Generate materials → you apply manually, OR
- Support only “easy apply” style integrations

---

What aspects do you want to drill into? I’m thinking the **Profile Store schema** and **CV personalisation logic** might be the most interesting to design next, given your RAG experience.