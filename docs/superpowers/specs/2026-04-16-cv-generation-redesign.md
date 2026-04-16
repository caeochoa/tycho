# CV Generation Redesign

**Date:** 2026-04-16  
**Status:** Approved — ready for implementation

## Context

Tycho's CV generation had two pain points:

1. **Profile authoring friction** — adding new experiences required writing mandatory `id` fields on every entry and bullet, manually duplicating content across three hardcoded focus-area variations (`ml_focus`, `backend_focus`, `data_focus`), and had no assisted authoring path.

2. **Template quality and extensibility** — the existing templates (`ats_resume`, `developer_cv`) were visually basic, each language variant was a separate duplicate file, and there was no way to drop in a new template without modifying source code.

The goal is to remove authoring friction, replace focus areas with a simpler tag-driven model, add optional LLM assistance at both authoring and generation time, and introduce a self-contained template repository system with two well-designed initial templates.

---

## Section 1: Profile Schema Simplification

### What changes

- **`id` fields removed** from bullets and experience/education/other entries. IDs are auto-derived internally from a hash of text + company + dates. No user-facing IDs needed.
- **`variations` block removed** from bullets. The `BulletVariations` and `SummaryVariations` Pydantic models are deleted.
- **`summary` flattened** — `personal.yaml` changes from `{default: "...", variations: {ml_focus: ...}}` to a plain string.
- **Backwards compatible** — existing `id` and `variations` fields are silently ignored on load. No forced migration.

### YAML before / after

```yaml
# BEFORE
- id: "oesia_rag"
  text: "Led backend development of OKM..."
  text_es: "Liderazgo del desarrollo..."
  tags: [rag, llm, python]
  priority: 1
  variations:
    ml_focus: "Architected RAG pipeline..."
    backend_focus: "Built full-stack platform..."

# AFTER
- text: "Led backend development of OKM..."
  text_es: "Liderazgo del desarrollo..."
  tags: [rag, llm, python]
  priority: 1
```

### Files affected

- `src/tycho/models.py` — remove `BulletVariations`, `SummaryVariations`; simplify `Bullet.variations` → removed, `Summary` → `str`; remove `TailoredBullet.id` (no longer meaningful without source bullet IDs)
- `src/tycho/cv/profile_loader.py` — stop requiring `id`; ignore `variations` on load

---

## Section 2: `tycho add-experience` Command

A new CLI command with two paths: an interactive wizard (always works, no LLM) and an LLM-assisted draft path (`--from-description`).

### Base wizard (no LLM)

```
$ tycho add-experience

Type:     [experience / education / other] → experience
Company:  Grupo Oesía
Title:    AI Engineer
Dates:    2024 - Present
Location: Madrid (optional)
Tags:     ai, rag, llm, python, langchain
Priority: 1

Bullet 1: Led backend development of OKM...
Tags for bullet 1 (enter to inherit entry tags): rag, llm, python
Bullet 2: (enter to finish)

✓ Saved to profile/experience/grupo_oesia_ai_engineer.yaml
```

Filename is auto-derived from company + title, slugified.

### LLM-assisted path (`--from-description`)

```
$ tycho add-experience --from-description

Paste a job description or your own notes (Ctrl+D when done):
> ...
^D

⠸ Drafting experience entry...

Review the generated YAML (edit then save, or discard):
────────────────────────────────────────
company: Grupo Oesía
title: AI Engineer
...
────────────────────────────────────────
[e]dit, [s]ave, [d]iscard: s

✓ Saved to profile/experience/grupo_oesia_ai_engineer.yaml
```

The LLM prompt includes the profile's existing tag vocabulary to ensure consistency. Gracefully degrades to wizard-only if no LLM is configured or if the LLM call fails.

### Files affected

- `src/tycho/cv/experience_builder.py` — **new module**: wizard logic + LLM draft
- `src/tycho/cli.py` — new `add-experience` command

---

## Section 3: Bullet Selection & LLM Tailoring at Generation Time

Replaces the focus-area detection system with two clean phases.

### Phase 1 — Tag scoring (always runs)

Each bullet is scored by tag overlap with the job's extracted keywords + priority bonus. Top N bullets per entry are selected. Identical to current behaviour minus the focus-area detour.

### Phase 2 — LLM rewriting (optional)

After Phase 1 selects bullets, the LLM rewrites **all selected bullets** for each entry to match the job's language and emphasis. The prompt instructs it not to invent facts or metrics. If the LLM call fails, the unmodified Phase 1 bullet texts are used as fallback.

```
Before: "Led backend development of OKM, a no-code RAG platform for enterprises."
After:  "Architected and led backend of OKM, an enterprise RAG platform enabling 
         no-code document QA and SQL query translation over internal data."
```

**Summary tailoring** follows the same pattern — default used as-is without LLM; tailored version generated when LLM available.

### What replaces what

| Removed | Replaced by |
|---------|-------------|
| `_detect_focus()` | — (deleted) |
| `_detect_focus_llm()` | — (deleted) |
| `_get_bullet_text()` variation logic | simple `bullet.text` / `bullet.text_es` lookup |
| `_llm_rerank_bullets()` (returns ordering) | `_llm_rewrite_bullets()` (returns rewritten text) |

### Files affected

- `src/tycho/cv/module_selector.py` — remove focus detection; add `_llm_rewrite_bullets()`

---

## Section 4: Template Repository System

### Folder structure

```
profile/templates/
├── awesome_cv/
│   ├── template.yaml       # metadata + declared params
│   ├── cv.tex.j2           # single file, handles en/es via Jinja2
│   └── awesome-cv.cls      # LaTeX class bundled with template
├── sidebar/
│   ├── template.yaml
│   └── cv.tex.j2
└── (any folder dropped here is auto-discovered)
```

Old flat files (`ats_resume.tex.j2`, `developer_cv.tex.j2`, `*_es.tex.j2`) are removed. Language variants are handled inside a single template via Jinja2 conditionals — no more duplicated files.

### `template.yaml` schema

```yaml
name: "Awesome CV"
description: "Clean typographic layout, configurable accent color"
ats_friendly: true
languages: [en, es]

params:
  accent_color:
    type: color
    default: "#0e76a8"
    label: "Header and rule color"
  font:
    type: choice
    options: [lmodern, raleway, sourcesanspro]
    default: lmodern
  show_photo:
    type: bool
    default: false
    label: "Include profile photo (requires photo_path in personal.yaml)"
```

### `config.yaml` override

```yaml
output:
  template: awesome_cv
  template_params:
    accent_color: "#2c3e50"
    font: raleway
```

### CLI

```
tycho templates                              # list all discovered templates + params
tycho generate <id> --template sidebar       # use specific template
tycho generate <id> -p accent_color=#e74c3c  # override a param inline
```

### Error on missing template

If `config.yaml` references a removed template name (`ats_resume`, `developer_cv`), Tycho prints:

```
Template 'ats_resume' not found. Available templates: awesome_cv, sidebar
Update output.template in config.yaml to continue.
```

### Files affected

- `src/tycho/cv/latex_builder.py` — template discovery via subdirectories; load `template.yaml`; merge params (defaults → config → CLI flags); pass params into Jinja2 context; copy any `.cls` files from the template folder into the temp compile directory so pdflatex/latexmk can resolve them
- `src/tycho/config.py` — add `template_params: dict[str, Any]` to `OutputConfig`
- `src/tycho/cli.py` — add `tycho templates` command; add `-p` flag to `generate`
- `profile/templates/` — replace flat files with `awesome_cv/` and `sidebar/` folders

---

## Section 5: New Templates

### `awesome_cv`

- Layout: dates-left / content-right, accent-coloured ruled section headers
- Font: Latin Modern (default), Raleway or Source Sans Pro (configurable)
- ATS-friendly: yes — single column, no images by default, standard encoding
- Ships with `awesome-cv.cls`
- Params: `accent_color`, `font`, `show_photo`

### `sidebar`

- Layout: dark sidebar (skills + contact), main column for experience
- Sidebar background: configurable dark colour, default `#1a1a2e`
- Accent for section rules and company names: configurable, default `#a0c4ff`
- Less ATS-friendly, best for roles where visual presentation matters
- Params: `sidebar_color`, `accent_color`, `sidebar_width`

---

## Section 6: Migration Path

### Automated migration (optional)

```
tycho migrate-profile --dry-run   # shows what would change
tycho migrate-profile             # rewrites YAMLs in place:
                                  #   removes id fields from bullets
                                  #   removes variations blocks
                                  #   flattens summary.default → summary string
```

### Files affected

- `src/tycho/cli.py` — new `migrate-profile` command
- `profile/` — YAML files rewritten in place (existing files are backwards compatible without migration)

---

## Full Change Summary

| File | Change |
|------|--------|
| `src/tycho/models.py` | Remove `BulletVariations`, `SummaryVariations`; simplify `Bullet`, `Summary` |
| `src/tycho/cv/profile_loader.py` | Stop requiring `id`; ignore `variations` on load |
| `src/tycho/cv/module_selector.py` | Remove focus detection; add `_llm_rewrite_bullets()` |
| `src/tycho/cv/latex_builder.py` | Subdir template discovery; load `template.yaml`; pass params to Jinja2 |
| `src/tycho/cv/experience_builder.py` | **New** — wizard + LLM draft logic |
| `src/tycho/config.py` | Add `template_params: dict[str, Any]` to `OutputConfig` |
| `src/tycho/cli.py` | Add `add-experience`, `templates`, `migrate-profile`; add `-p` to `generate` |
| `profile/templates/` | Replace flat `.tex.j2` files with `awesome_cv/` and `sidebar/` folders |
| `tests/` | Update profile/scorer tests; add tests for experience_builder, template discovery |

---

## Verification

1. `tycho profile` — validates existing YAML files load cleanly with old `id`/`variations` fields present
2. `tycho add-experience` — wizard creates a valid YAML file; `tycho profile` accepts it
3. `tycho add-experience --from-description` — LLM draft produced, saved, accepted by `tycho profile`
4. `tycho generate <id>` — PDF produced using `awesome_cv` template
5. `tycho generate <id> --template sidebar` — PDF produced using `sidebar` template
6. `tycho generate <id> -p accent_color=#e74c3c` — accent colour reflected in output PDF
7. `tycho generate <id> --lang es` — Spanish output works from single template file
8. `tycho templates` — lists both templates with their params
9. `tycho migrate-profile` — cleans up existing YAML files; `tycho profile` still validates
10. `pytest tests/` — all tests pass
