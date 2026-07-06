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

Parse failures are never silent: a WARNING is logged naming the key,
and the caller-supplied default (when given) is returned instead of a
misleading 0 / 0.0.
"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

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


def _coerce(value: Any, base_type: str, default: Any = None, key: str = None) -> Any:
    """Coerce a raw value to its concrete Python type.

    On an unparseable value, log a WARNING naming the config key and
    return `default` when one was supplied (falling back to a typed
    zero only as a last resort).
    """
    if base_type == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            logger.warning(
                "Config key %r: value %r is not a valid float; using default %r",
                key, value, default if default is not None else 0.0,
            )
            return float(default) if default is not None else 0.0
    if base_type == "int":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            logger.warning(
                "Config key %r: value %r is not a valid int; using default %r",
                key, value, default if default is not None else 0,
            )
            return int(default) if default is not None else 0
    if base_type == "bool":
        if isinstance(value, bool):
            return value
        if value is None:
            if default is not None:
                logger.warning(
                    "Config key %r: missing bool value; using default %r",
                    key, default,
                )
                return bool(default)
            return False
        return str(value).strip().lower() in ("true", "1", "yes")
    if base_type == "json":
        if isinstance(value, (list, dict)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            logger.warning(
                "Config key %r: value is not valid JSON; using default %r",
                key, default,
            )
            return default if default is not None else value
    return value


def resolve_value(
    raw_value: Any,
    value_type: str,
    tier: str,
    default: Any = None,
    key: str = None,
) -> Any:
    """Resolve a transaction_config row's stored value to the concrete
    value that applies for `tier` ('low' | 'medium' | 'high').

    For a tiered setting the stored value is JSON {low,medium,high};
    the requested tier is picked (falling back to 'medium', then to
    any available tier). A scalar setting is simply coerced.

    `default` (optional) is returned when the stored value cannot be
    parsed — pass the built-in default for the key so a corrupt row
    degrades to documented behaviour instead of 0. `key` is used only
    for log messages.
    """
    vt = value_type or "string"
    if is_tiered(vt):
        base = vt[len("tiered_"):]
        obj: Any = raw_value
        if isinstance(raw_value, str):
            try:
                obj = json.loads(raw_value)
            except (TypeError, ValueError):
                logger.warning(
                    "Config key %r: tiered value %r is not valid JSON; "
                    "using default %r", key, raw_value, default,
                )
                obj = {}
        if not isinstance(obj, dict):
            logger.warning(
                "Config key %r: tiered value is not an object; using default %r",
                key, default,
            )
            obj = {}
        picked = obj.get(tier)
        if picked is None:
            picked = obj.get("medium")
        if picked is None:
            for t in RISK_TIERS:
                if obj.get(t) is not None:
                    picked = obj.get(t)
                    break
        if picked is None and default is not None:
            return default
        return _coerce(picked, base, default=default, key=key)
    return _coerce(raw_value, vt, default=default, key=key)
