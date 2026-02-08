"""Typer CLI entry point for Tycho."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tycho.config import load_config

app = typer.Typer(
    name="tycho",
    help="Tycho — Automated Job Application Platform",
    no_args_is_help=True,
)
console = Console()


def _get_config():
    return load_config(Path("config.yaml"))


def _get_db():
    from tycho.db import get_session, init_db

    config = _get_config()
    engine = init_db(config.db_path)
    return get_session(engine)


def _get_llm_client():
    """Get LLM client if available, or None."""
    config = _get_config()
    if not config.llm.enabled:
        return None

    from tycho.llm import get_llm_client

    client = get_llm_client(config.llm)
    if client.available:
        return client
    return None


@app.command()
def collect(
    terms: list[str] | None = typer.Option(None, "--term", "-t", help="Search terms (overrides config)"),
    locations: list[str] | None = typer.Option(None, "--location", "-l", help="Locations (overrides config)"),
):
    """Collect jobs from LinkedIn and Indeed."""
    config = _get_config()
    search_terms = terms or config.search.terms
    search_locations = locations or config.search.locations

    console.print(f"[bold]Collecting jobs...[/bold]")
    console.print(f"  Terms: {', '.join(search_terms)}")
    console.print(f"  Locations: {', '.join(search_locations)}")

    from tycho.collector.jobspy_collector import JobSpyCollector
    from tycho.collector.normalize import deduplicate
    from tycho.db import get_session, init_db, upsert_job

    collector = JobSpyCollector(country=config.search.country)
    raw_jobs = collector.collect(
        search_terms=search_terms,
        locations=search_locations,
        results_wanted=config.search.results_per_source,
    )

    console.print(f"  Collected [bold]{len(raw_jobs)}[/bold] raw jobs")

    jobs = deduplicate(raw_jobs)
    console.print(f"  After dedup: [bold]{len(jobs)}[/bold] unique jobs")

    # Score jobs
    from tycho.cv.profile_loader import load_profile
    from tycho.matcher.scorer import score_jobs

    try:
        profile = load_profile(config.profile_dir)
        llm_client = _get_llm_client()
        if llm_client:
            console.print("  [cyan]Using LLM-enhanced keyword extraction[/cyan]")
        jobs = score_jobs(jobs, profile, config.scoring, llm_client=llm_client)
        console.print("  [green]Scored all jobs against profile[/green]")
    except Exception as e:
        console.print(f"  [yellow]Skipping scoring: {e}[/yellow]")

    # Store in database
    engine = init_db(config.db_path)
    session = get_session(engine)
    new_count = 0
    for job in jobs:
        if upsert_job(session, job):
            new_count += 1
    session.commit()
    session.close()

    console.print(f"\n[bold green]Done![/bold green] {new_count} new jobs added, {len(jobs) - new_count} updated.")


@app.command()
def jobs(
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results"),
    min_score: float | None = typer.Option(None, "--min-score", help="Minimum match score"),
):
    """List collected jobs."""
    from tycho.db import get_jobs

    session = _get_db()
    job_list = get_jobs(session, status=status, min_score=min_score, limit=limit)
    session.close()

    if not job_list:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    table = Table(title=f"Jobs ({len(job_list)} results)")
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Title", style="bold", max_width=35)
    table.add_column("Company", max_width=20)
    table.add_column("Location", max_width=20)
    table.add_column("Status", width=10)
    table.add_column("Source", width=8)

    for job in job_list:
        score_str = f"{job.score:.2f}" if job.score is not None else "—"
        score_style = ""
        if job.score is not None:
            if job.score >= 0.75:
                score_style = "bold green"
            elif job.score >= 0.50:
                score_style = "yellow"
            else:
                score_style = "dim"

        status_style = {
            "new": "cyan",
            "interested": "green",
            "applied": "blue",
            "rejected": "red",
            "archived": "dim",
        }.get(job.status.value, "")

        table.add_row(
            job.id[:8],
            Text(score_str, style=score_style),
            job.title,
            job.company,
            job.location,
            Text(job.status.value, style=status_style),
            job.source,
        )

    console.print(table)


@app.command()
def show(
    job_id: str = typer.Argument(help="Job ID (or prefix)"),
):
    """Show job details and match breakdown."""
    from tycho.db import get_job_by_id, get_jobs

    session = _get_db()

    # Try exact match first, then prefix match
    job = get_job_by_id(session, job_id)
    if not job:
        all_jobs = get_jobs(session, limit=10000)
        matches = [j for j in all_jobs if j.id.startswith(job_id)]
        if len(matches) == 1:
            job = matches[0]
        elif len(matches) > 1:
            console.print(f"[yellow]Multiple matches for '{job_id}':[/yellow]")
            for m in matches[:5]:
                console.print(f"  {m.id[:8]}  {m.title} @ {m.company}")
            session.close()
            return
        else:
            console.print(f"[red]Job not found: {job_id}[/red]")
            session.close()
            return

    session.close()

    # Display job details
    panel_content = (
        f"[bold]{job.title}[/bold]\n"
        f"Company: {job.company}\n"
        f"Location: {job.location}\n"
        f"Source: {job.source}\n"
        f"Status: {job.status.value}\n"
        f"URL: {job.url}\n"
    )
    if job.salary_min or job.salary_max:
        panel_content += f"Salary: {job.salary_min or '?'} - {job.salary_max or '?'}\n"
    if job.date_posted:
        panel_content += f"Posted: {job.date_posted.strftime('%Y-%m-%d')}\n"

    console.print(Panel(panel_content, title=f"Job {job.id[:8]}", expand=False))

    # Score breakdown
    if job.score is not None:
        console.print(f"\n[bold]Match Score: {job.score:.3f}[/bold]")
        if job.score_details:
            details = job.score_details
            table = Table(title="Score Breakdown")
            table.add_column("Component", style="bold")
            table.add_column("Score", justify="right")

            for key in ["keyword_match", "title_match", "skills_overlap", "location_match"]:
                if key in details:
                    table.add_row(key.replace("_", " ").title(), f"{details[key]:.3f}")

            console.print(table)

            if "job_keywords" in details:
                kws = details["job_keywords"]
                console.print(f"\n[bold]Detected Keywords ({len(kws)}):[/bold] {', '.join(kws)}")

    # Description excerpt
    if job.description:
        desc = job.description[:500]
        if len(job.description) > 500:
            desc += "..."
        console.print(f"\n[bold]Description:[/bold]\n{desc}")


@app.command()
def generate(
    job_id: str = typer.Argument(help="Job ID (or prefix)"),
    formats: str = typer.Option(None, "--format", "-f", help="Output formats: pdf,tex,docx (comma-separated)"),
    lang: str = typer.Option(None, "--lang", help="Language: en or es"),
    template: str = typer.Option(None, "--template", "-t", help="LaTeX template: ats_resume, developer_cv"),
    cover_letter: bool = typer.Option(False, "--cover-letter", "--cl", help="Generate a cover letter"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Disable LLM features for this run"),
):
    """Generate a tailored CV for a job."""
    from tycho.cv.latex_builder import build_pdf, build_tex
    from tycho.cv.module_selector import select_modules
    from tycho.cv.profile_loader import load_profile
    from tycho.db import get_job_by_id, get_jobs, update_job_paths

    config = _get_config()
    session = _get_db()

    # Find job
    job = get_job_by_id(session, job_id)
    if not job:
        all_jobs = get_jobs(session, limit=10000)
        matches = [j for j in all_jobs if j.id.startswith(job_id)]
        if len(matches) == 1:
            job = matches[0]
        else:
            console.print(f"[red]Job not found or ambiguous: {job_id}[/red]")
            session.close()
            return

    language = lang or config.output.language
    template_name = template or config.output.template
    output_formats = (formats or ",".join(config.output.formats)).split(",")

    # Get LLM client
    llm_client = None if no_llm else _get_llm_client()
    if llm_client:
        console.print("  [cyan]LLM-enhanced generation enabled[/cyan]")

    console.print(f"[bold]Generating CV for:[/bold] {job.title} @ {job.company}")
    console.print(f"  Language: {language}, Template: {template_name}, Formats: {', '.join(output_formats)}")

    # Load profile and tailor
    profile = load_profile(config.profile_dir)
    tailored = select_modules(profile, job, language=language, llm_client=llm_client)

    template_dir = Path(config.profile_dir) / "templates"
    output_dir = Path(config.output_dir) / _safe_filename(f"{job.company}_{job.title}")
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_paths = []

    if "pdf" in output_formats:
        pdf_path = output_dir / f"CV_{language.upper()}.pdf"
        try:
            result = build_pdf(tailored, template_dir, pdf_path, language=language, country=config.search.country, template=template_name)
            console.print(f"  [green]PDF generated:[/green] {result}")
            generated_paths.append(str(result))
        except RuntimeError as e:
            console.print(f"  [red]PDF failed:[/red] {e}")
            # Fall back to .tex
            tex_path = output_dir / f"CV_{language.upper()}.tex"
            result = build_tex(tailored, template_dir, tex_path, language=language, country=config.search.country, template=template_name)
            console.print(f"  [yellow]LaTeX source saved:[/yellow] {result}")
            generated_paths.append(str(result))

    if "tex" in output_formats:
        tex_path = output_dir / f"CV_{language.upper()}.tex"
        result = build_tex(tailored, template_dir, tex_path, language=language, country=config.search.country, template=template_name)
        console.print(f"  [green]LaTeX source saved:[/green] {result}")
        generated_paths.append(str(result))

    if "docx" in output_formats:
        from tycho.cv.docx_builder import build_docx

        docx_path = output_dir / f"CV_{language.upper()}.docx"
        result = build_docx(tailored, docx_path, language=language, country=config.search.country)
        console.print(f"  [green]DOCX generated:[/green] {result}")
        generated_paths.append(str(result))

    # Cover letter generation
    cl_path = None
    if cover_letter:
        if llm_client is None:
            console.print("  [yellow]Cover letter requires LLM. Set ANTHROPIC_API_KEY or configure another provider.[/yellow]")
        else:
            from tycho.cover_letter.generator import generate_cover_letter, save_cover_letter

            console.print("  [cyan]Generating cover letter...[/cyan]")
            try:
                cl = generate_cover_letter(
                    job=job,
                    profile=profile,
                    tailored=tailored,
                    llm_client=llm_client,
                    config=config.cover_letter,
                    language=language,
                )

                # Save as .txt
                txt_path = output_dir / f"CoverLetter_{language.upper()}.txt"
                save_cover_letter(cl, txt_path, format="txt")
                console.print(f"  [green]Cover letter (txt):[/green] {txt_path}")

                # Save as .docx
                docx_cl_path = output_dir / f"CoverLetter_{language.upper()}.docx"
                save_cover_letter(cl, docx_cl_path, format="docx")
                console.print(f"  [green]Cover letter (docx):[/green] {docx_cl_path}")

                cl_path = str(txt_path)
            except Exception as e:
                console.print(f"  [red]Cover letter failed:[/red] {e}")

    # Update DB
    if generated_paths or cl_path:
        update_job_paths(
            session,
            job.id,
            cv_path=generated_paths[0] if generated_paths else None,
            cover_letter_path=cl_path,
        )
        session.commit()

    session.close()
    console.print(f"\n[bold green]Done![/bold green] Output: {output_dir}")


@app.command()
def mark(
    job_id: str = typer.Argument(help="Job ID (or prefix)"),
    status: str = typer.Argument(help="New status: interested, rejected, applied, archived, reviewed"),
):
    """Mark a job with a status."""
    from tycho.db import get_job_by_id, get_jobs, update_job_status

    valid_statuses = {"new", "reviewed", "interested", "applied", "rejected", "archived"}
    if status not in valid_statuses:
        console.print(f"[red]Invalid status: {status}[/red]. Valid: {', '.join(sorted(valid_statuses))}")
        return

    session = _get_db()

    # Find job by exact or prefix match
    job = get_job_by_id(session, job_id)
    if not job:
        all_jobs = get_jobs(session, limit=10000)
        matches = [j for j in all_jobs if j.id.startswith(job_id)]
        if len(matches) == 1:
            job = matches[0]
        else:
            console.print(f"[red]Job not found or ambiguous: {job_id}[/red]")
            session.close()
            return

    old_status = job.status.value
    update_job_status(session, job.id, status)
    session.commit()
    session.close()

    console.print(f"[bold]{job.title}[/bold] @ {job.company}: {old_status} → [green]{status}[/green]")


@app.command()
def profile():
    """Validate all profile YAML modules."""
    from tycho.cv.profile_loader import load_profile, validate_profile

    config = _get_config()
    profile_dir = config.profile_dir

    console.print(f"[bold]Validating profile in:[/bold] {profile_dir}/")

    errors = validate_profile(profile_dir)
    if errors:
        for err in errors:
            console.print(f"  [red]✗[/red] {err}")
        raise typer.Exit(1)

    # Load and display summary
    p = load_profile(profile_dir)
    console.print(f"  [green]✓[/green] Personal: {p.personal.name}")
    console.print(f"  [green]✓[/green] Skills: {len(p.skills.technical)} technical, {len(p.skills.languages)} languages")
    console.print(f"  [green]✓[/green] Experience: {len(p.experience)} entries")
    for exp in p.experience:
        bullet_count = len(exp.bullets)
        console.print(f"      - {exp.title} @ {exp.company} ({bullet_count} bullets)")
    console.print(f"  [green]✓[/green] Education: {len(p.education)} entries")
    for edu in p.education:
        console.print(f"      - {edu.degree} @ {edu.institution}")
    console.print(f"  [green]✓[/green] Other: {len(p.other)} entries")
    for oth in p.other:
        console.print(f"      - {oth.title} @ {oth.organization}")

    console.print(f"\n[bold green]Profile valid![/bold green]")


@app.command()
def dashboard():
    """Interactive job browsing dashboard (Rich)."""
    from tycho.db import get_jobs

    session = _get_db()
    all_jobs = get_jobs(session, limit=200)
    session.close()

    if not all_jobs:
        console.print("[yellow]No jobs collected yet. Run 'tycho collect' first.[/yellow]")
        return

    # Summary stats
    statuses = {}
    cvs_generated = 0
    cls_generated = 0
    for j in all_jobs:
        s = j.status.value
        statuses[s] = statuses.get(s, 0) + 1
        if j.cv_path:
            cvs_generated += 1
        if j.cover_letter_path:
            cls_generated += 1

    scored = [j for j in all_jobs if j.score is not None]
    avg_score = sum(j.score for j in scored) / len(scored) if scored else 0

    console.print(Panel(
        f"[bold]Total Jobs:[/bold] {len(all_jobs)}\n"
        f"[bold]Average Score:[/bold] {avg_score:.3f}\n"
        f"[bold]CVs Generated:[/bold] {cvs_generated}\n"
        f"[bold]Cover Letters:[/bold] {cls_generated}\n"
        f"[bold]Status:[/bold] " + ", ".join(f"{k}: {v}" for k, v in sorted(statuses.items())),
        title="Dashboard",
    ))

    # Top jobs
    top = sorted([j for j in all_jobs if j.score is not None], key=lambda j: j.score, reverse=True)[:10]
    if top:
        table = Table(title="Top 10 Jobs by Score")
        table.add_column("ID", style="dim", max_width=8)
        table.add_column("Score", justify="right", width=6)
        table.add_column("Title", style="bold", max_width=35)
        table.add_column("Company", max_width=20)
        table.add_column("Location", max_width=20)
        table.add_column("Status", width=10)

        for job in top:
            score_style = "bold green" if job.score >= 0.75 else ("yellow" if job.score >= 0.5 else "dim")
            table.add_row(
                job.id[:8],
                Text(f"{job.score:.2f}", style=score_style),
                job.title,
                job.company,
                job.location,
                job.status.value,
            )

        console.print(table)

    console.print("\n[dim]Use 'tycho show <id>' to view details, 'tycho mark <id> interested' to mark.[/dim]")


@app.command()
def serve(
    host: str = typer.Option(None, "--host", "-h", help="Bind host (default: from config)"),
    port: int = typer.Option(None, "--port", "-p", help="Bind port (default: from config)"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
    no_bot: bool = typer.Option(False, "--no-bot", help="Disable Telegram bot"),
):
    """Start the web dashboard."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Web dependencies not installed. Run: pip install tycho[web][/red]")
        raise typer.Exit(1)

    config = _get_config()
    bind_host = host or config.web.host
    bind_port = port or config.web.port
    do_reload = reload or config.web.reload

    if no_bot:
        config.telegram.enabled = False

    console.print(f"[bold]Starting Tycho web dashboard[/bold]")
    console.print(f"  http://{bind_host}:{bind_port}")

    if config.telegram.enabled and config.telegram.effective_token:
        console.print("  Telegram bot: [green]enabled[/green]")
    else:
        console.print("  Telegram bot: [dim]disabled[/dim]")

    uvicorn.run(
        "tycho.web.app:create_app",
        host=bind_host,
        port=bind_port,
        reload=do_reload,
        factory=True,
    )


@app.command()
def config_cmd():
    """Show current configuration."""
    config = _get_config()
    console.print(Panel(str(config.model_dump_json(indent=2)), title="Configuration"))


def _safe_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    import re
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:80]


if __name__ == "__main__":
    app()
