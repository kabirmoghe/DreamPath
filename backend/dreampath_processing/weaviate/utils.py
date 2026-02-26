import pandas as pd


def safe_float(value):
    """Convert value to float, handling NaN/None."""
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value):
    """Convert value to int, handling NaN/None."""
    if pd.isna(value):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def safe_str(value):
    """Convert value to str, handling NaN/None."""
    if pd.isna(value) or value in ["", "nan", "None"]:
        return None
    return str(value).strip()


def parse_pipe_list(value) -> list[str]:
    """Parse a pipe-separated string into a list of non-empty stripped strings."""
    if not value or (isinstance(value, float) and pd.isna(value)):
        return []
    return [v.strip() for v in str(value).split("|") if v.strip()]
