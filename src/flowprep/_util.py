"""Shared config-parsing helpers for tool modules.

The visual canvas sends untouched numeric fields as empty strings, and
hand-written / LLM-generated workflow JSON often uses nulls. Tools should
treat ``""`` / ``None`` as "use the default" instead of crashing with a
raw ``int('')`` ValueError.
"""
from __future__ import annotations


def num_float(cfg: dict, key: str, default: float) -> float:
    v = cfg.get(key, default)
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return float(default)
    return float(v)


def num_int(cfg: dict, key: str, default: int) -> int:
    v = cfg.get(key, default)
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return int(default)
    return int(float(v)) if isinstance(v, str) else int(v)


def opt_int(cfg: dict, key: str):
    """Like num_int but returns None when the field is blank - for
    'either n or frac' style configs where blank means 'not chosen'."""
    v = cfg.get(key)
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    return int(float(v)) if isinstance(v, str) else int(v)


def opt_float(cfg: dict, key: str):
    v = cfg.get(key)
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    return float(v)


def as_list(v) -> list:
    """Accept a list, a comma-separated string, or a single value."""
    if v is None or v == "":
        return []
    if isinstance(v, str):
        return [s.strip() for s in v.split(",") if s.strip()]
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]
