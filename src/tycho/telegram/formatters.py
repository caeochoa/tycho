"""Format Job data into Telegram HTML messages."""

from html import escape

# Emoji constants using proper Unicode codepoints
_GREEN_CIRCLE = "\U0001f7e2"
_YELLOW_CIRCLE = "\U0001f7e1"
_RED_CIRCLE = "\U0001f534"
_WHITE_CIRCLE = "\u26aa"
_OFFICE = "\U0001f3e2"
_PIN = "\U0001f4cd"
_CHART = "\U0001f4ca"
_MONEY = "\U0001f4b0"
_TAG = "\U0001f3f7"
_KEY = "\U0001f511"
_CALENDAR = "\U0001f4c5"
_CHECK = "\u2705"
_CROSS = "\u274c"


def _score_emoji(score: float | None) -> str:
    if score is None:
        return _WHITE_CIRCLE
    if score >= 0.75:
        return _GREEN_CIRCLE
    if score >= 0.50:
        return _YELLOW_CIRCLE
    return _RED_CIRCLE


def format_job_line(job, index: int) -> str:
    """One-line summary: index. emoji score — title @ company (location)."""
    score_str = f"{job.score:.2f}" if job.score is not None else "-.--"
    emoji = _score_emoji(job.score)
    location = f" ({escape(job.location)})" if job.location else ""
    return (
        f"{index}. {emoji} {score_str} \u2014 "
        f"{escape(job.title)} @ {escape(job.company)}{location}"
    )


def format_job_detail(job, thresholds=None) -> str:
    """Multi-line HTML detail view for a single job."""
    lines = [f"<b>{escape(job.title)}</b>"]
    lines.append(f"{_OFFICE} {escape(job.company)} \u00b7 {_PIN} {escape(job.location or 'N/A')}")

    # Score
    if job.score is not None:
        lines.append(f"{_CHART} Score: {job.score:.2f}")
        if job.score_details:
            d = job.score_details
            parts = []
            for key in ["keyword_match", "title_match", "skills_overlap", "location_match"]:
                if key in d:
                    label = key.replace("_", " ").title()
                    parts.append(f"{label}: {d[key]:.2f}")
            if parts:
                lines.append("  \u2022 " + " \u2022 ".join(parts))

    # Salary
    if job.salary_min or job.salary_max:
        sal_min = f"{job.salary_min:,.0f}" if job.salary_min else "?"
        sal_max = f"{job.salary_max:,.0f}" if job.salary_max else "?"
        lines.append(f"{_MONEY} {sal_min} \u2013 {sal_max}")

    lines.append(f"{_TAG} Status: {job.status.value}")

    # Keywords
    if job.score_details and "job_keywords" in job.score_details:
        kws = job.score_details["job_keywords"][:10]
        lines.append(f"{_KEY} Keywords: {', '.join(escape(k) for k in kws)}")

    # Description excerpt
    if job.description:
        desc = job.description[:300]
        if len(job.description) > 300:
            desc += "..."
        lines.append(f"\n{escape(desc)}")

    return "\n".join(lines)


def format_schedule_status(config, runs, next_run) -> str:
    """Format scheduler status panel."""
    lines = [f"{_CALENDAR} <b>Scheduler</b>"]

    if config.scheduler.enabled:
        lines.append("Status: Active")
        lines.append(f"Cron: {escape(config.scheduler.cron)}")
        if next_run:
            lines.append(f"Next run: {next_run.strftime('%Y-%m-%d %H:%M')}")
    else:
        lines.append("Status: Disabled")

    if runs:
        lines.append("\nRecent runs:")
        for run in runs[:5]:
            emoji = _CHECK if run.status == "success" else _CROSS
            ts = run.timestamp.strftime("%b %d, %H:%M")
            lines.append(
                f"{emoji} {ts} \u2014 {run.raw_count} raw, "
                f"{run.deduped_count} dedup, {run.new_count} new"
            )

    return "\n".join(lines)
