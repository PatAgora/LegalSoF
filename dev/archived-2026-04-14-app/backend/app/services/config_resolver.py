"""
Risk-tiered configuration resolution.

Most platform rules can be tuned differently for low-, medium- and
high-risk clients. A tiered setting stores its value as a JSON object
keyed by tier — {"low": ..., "medium": ..., "high": ...} — with a
value_type of 'tiered_float', 'tiered_int' or 'tiered_bool'. A scalar
setting keeps a plain value and a plain value_type ('float', 'int',
'bool', 'string', 'json').

resolve_value() turns a stored config row into the concrete value that
applies to a given matter, based on that matter's risk rating.
"""
import json
from typing import Any

RISK_TIERS = ("low", "medium", "high")


def map_risk_tier(risk_rating: Any) -> str:
    """Map a Matter risk rating onto one of the three config tiers.

    Critical-rated matters use the High tier — the strictest settings.
    """
    r = str(risk_rating or "medium").strip().lower()
    if r in ("critical", "high"):
        return "high"
    if r == "low":
        return "low"
    return "medium"


def is_tiered(value_type: str) -> bool:
    return bool(value_type) and value_type.startswith("tiered_")


def _coerce(value: Any, base_type: str) -> Any:
    """Coerce a raw value to its concrete Python type."""
    if base_type == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    if base_type == "int":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    if base_type == "bool":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes")
    if base_type == "json":
        if isinstance(value, (list, dict)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value


def resolve_value(raw_value: Any, value_type: str, tier: str) -> Any:
    """Resolve a transaction_config row's stored value to the concrete
    value that applies for `tier` ('low' | 'medium' | 'high').

    For a tiered setting the stored value is JSON {low,medium,high};
    the requested tier is picked (falling back to 'medium', then to
    any available tier). A scalar setting is simply coerced.
    """
    vt = value_type or "string"
    if is_tiered(vt):
        base = vt[len("tiered_"):]
        obj: Any = raw_value
        if isinstance(raw_value, str):
            try:
                obj = json.loads(raw_value)
            except (TypeError, ValueError):
                obj = {}
        if not isinstance(obj, dict):
            obj = {}
        picked = obj.get(tier)
        if picked is None:
            picked = obj.get("medium")
        if picked is None:
            for t in RISK_TIERS:
                if obj.get(t) is not None:
                    picked = obj.get(t)
                    break
        return _coerce(picked, base)
    return _coerce(raw_value, vt)
