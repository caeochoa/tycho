"""Age helpers for job postings, shared by scoring, CLI, and web display."""

from datetime import datetime


def age_days(dt: datetime | None, fallback: datetime | None = None) -> float | None:
    """Days elapsed since `dt` (or `fallback` if `dt` is None). None if both missing."""
    effective = dt or fallback
    if effective is None:
        return None
    delta = datetime.now() - effective
    return max(0.0, delta.total_seconds() / 86400)


def age_label(dt: datetime | None) -> str:
    """Compact human age label: '3d', '2w', '5mo', '1y', or '—' for unknown."""
    days = age_days(dt)
    if days is None:
        return "—"
    days = int(days)
    if days < 7:
        return f"{days}d"
    if days < 30:
        return f"{days // 7}w"
    if days < 365:
        return f"{days // 30}mo"
    return f"{days // 365}y"
