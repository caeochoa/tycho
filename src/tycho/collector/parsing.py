"""Defensive value parsing shared by job collectors."""

from datetime import datetime


def parse_str(val) -> str:
    """Safely parse a string value, mapping None/NaN to '' instead of 'nan'/'None'."""
    if val is None:
        return ""
    try:
        import pandas as pd
        if pd.isna(val):
            return ""
    except (TypeError, ValueError, ImportError):
        pass
    return str(val)


def parse_float(val) -> float | None:
    """Safely parse a float value."""
    if val is None:
        return None
    try:
        import math
        f = float(val)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def parse_date(val) -> datetime | None:
    """Safely parse a date value."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return _to_naive_local(val)
    try:
        import pandas as pd
        if pd.isna(val):
            return None
        text = str(val).strip()
        # ATS APIs use 'Z' / ' UTC' suffixes that fromisoformat may reject.
        if text.endswith(" UTC"):
            text = text[:-4] + "+00:00"
        elif text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return _to_naive_local(datetime.fromisoformat(text))
    except (ValueError, TypeError, ImportError):
        return None


def _to_naive_local(dt: datetime) -> datetime:
    """Convert aware datetimes to naive local time (the app compares against datetime.now())."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone().replace(tzinfo=None)
