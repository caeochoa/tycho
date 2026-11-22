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
        return val
    try:
        import pandas as pd
        if pd.isna(val):
            return None
        return datetime.fromisoformat(str(val))
    except (ValueError, TypeError, ImportError):
        return None
