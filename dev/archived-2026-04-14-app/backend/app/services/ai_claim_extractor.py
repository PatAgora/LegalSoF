"""
AI-assisted Source of Funds claim extraction.

Turns a free-text client SoF explanation into a structured list of
claims (source type, amount, date, description) using a large language
model. This removes the dependence on an exact-phrase keyword bank —
the model understands paraphrasing, so unusual wording is still
captured.

Provider-agnostic: the active provider is chosen by the AI_PROVIDER
setting ('anthropic' or 'gemini'). Anthropic is the current default;
switching to Google later is a config change only — set
AI_PROVIDER=gemini and GEMINI_API_KEY.

IMPORTANT — this calls an EXTERNAL API. Client AML data (names,
amounts, fund origins) is sent to the provider. This is a deliberate
product decision; ensure a data-processing agreement is in place and
that clients are informed. When the active provider's API key is not
configured the caller falls back to the local deterministic parser.
"""
from typing import Any, Dict, List, Optional
import json

import httpx

from app.core.config import settings

# Controlled vocabulary the model must map every source onto. Keeping
# this fixed means downstream code (claim matching, the report, the
# funds-lineage trigger) sees consistent type strings.
_ALLOWED_SOURCE_TYPES = [
    "property_sale", "business_sale", "savings", "inheritance", "gift",
    "pension", "salary", "investment", "loan", "compensation",
    "insurance", "lottery", "other",
]

_PROMPT = (
    "You are an anti-money-laundering analyst assistant for a UK law firm. "
    "Read the client's Source of Funds explanation below and identify EVERY "
    "distinct source of funds the client describes.\n\n"
    "Rules:\n"
    "- One entry per distinct source. If the client mentions three sources, "
    "return three entries.\n"
    "- source_type MUST be one of: " + ", ".join(_ALLOWED_SOURCE_TYPES) + ".\n"
    "- amount is the figure in GBP as a plain number (no symbols, no commas). "
    "Where the client states BOTH a gross figure and a net figure for the "
    "same source (e.g. 'sold for 425000 with net proceeds of 269280'), use "
    "the NET figure — the money that actually reached the client.\n"
    "- Convert shorthand: '50k' = 50000, '1.2m' = 1200000.\n"
    "- date: the relevant date for the source (completion date, distribution "
    "date, etc.) as written, or an empty string if none is given.\n"
    "- description: a short plain-English summary of that source.\n"
    "- If the text genuinely describes no identifiable source of funds, "
    "return an empty list.\n\n"
    "Client explanation:\n\"\"\"\n{explanation}\n\"\"\"\n"
)

# Shared JSON-schema fragment for one source entry.
_SOURCE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "source_type": {"type": "string", "enum": _ALLOWED_SOURCE_TYPES},
        "amount":      {"type": "number"},
        "currency":    {"type": "string"},
        "date":        {"type": "string"},
        "description": {"type": "string"},
    },
    "required": ["source_type", "amount"],
}


def _active_provider() -> str:
    return (getattr(settings, "AI_PROVIDER", "anthropic") or "anthropic").strip().lower()


def is_configured() -> bool:
    """True when the active provider has an API key configured."""
    provider = _active_provider()
    if provider == "gemini":
        return bool(getattr(settings, "GEMINI_API_KEY", ""))
    return bool(getattr(settings, "ANTHROPIC_API_KEY", ""))


def extract_sources(explanation: str, timeout: float = 25.0) -> Optional[List[Dict[str, Any]]]:
    """Extract structured sources of funds from a free-text explanation.

    Returns a list of source dicts shaped like the structured-JSON
    'sources' array the assessment engine already understands, or None
    if the provider is not configured or the call fails (so the caller
    can fall back to the deterministic parser). An empty list is a
    valid successful result meaning 'no sources found'.
    """
    if not is_configured():
        return None
    text = (explanation or "").strip()
    if not text:
        return []

    provider = _active_provider()
    try:
        if provider == "gemini":
            raw_items = _call_gemini(text, timeout)
        else:
            raw_items = _call_anthropic(text, timeout)
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"[ai_extract] {provider} extraction error: {type(exc).__name__}: {exc}")
        return None

    if raw_items is None:
        return None
    return _normalise(raw_items)


# ---------------------------------------------------------------------------
# Anthropic (Claude) — current default
# ---------------------------------------------------------------------------

def _call_anthropic(text: str, timeout: float) -> Optional[List[Any]]:
    """Call the Anthropic Messages API with a forced tool call so the
    model returns a structured sources list rather than free text."""
    model = getattr(settings, "ANTHROPIC_MODEL", "") or "claude-haiku-4-5-20251001"
    tool = {
        "name": "record_sources_of_funds",
        "description": "Record every distinct source of funds the client described.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sources": {"type": "array", "items": _SOURCE_ITEM_SCHEMA},
            },
            "required": ["sources"],
        },
    }
    payload = {
        "model": model,
        "max_tokens": 1500,
        "tools": [tool],
        "tool_choice": {"type": "tool", "name": "record_sources_of_funds"},
        "messages": [
            {"role": "user", "content": _PROMPT.format(explanation=text[:12000])}
        ],
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
    if resp.status_code != 200:
        print(f"[ai_extract] anthropic HTTP {resp.status_code}: {resp.text[:300]}")
        return None
    data = resp.json()
    for block in data.get("content", []):
        if block.get("type") == "tool_use":
            sources = (block.get("input") or {}).get("sources")
            if isinstance(sources, list):
                return sources
    print(f"[ai_extract] anthropic — no tool_use block in response")
    return None


# ---------------------------------------------------------------------------
# Google Gemini — available now, intended as the later default
# ---------------------------------------------------------------------------

def _call_gemini(text: str, timeout: float) -> Optional[List[Any]]:
    """Call the Gemini generateContent API with a JSON response schema."""
    model = getattr(settings, "GEMINI_MODEL", "") or "gemini-2.0-flash"
    schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "source_type": {"type": "STRING", "enum": _ALLOWED_SOURCE_TYPES},
                "amount":      {"type": "NUMBER"},
                "currency":    {"type": "STRING"},
                "date":        {"type": "STRING"},
                "description": {"type": "STRING"},
            },
            "required": ["source_type", "amount"],
        },
    }
    payload = {
        "contents": [{"parts": [{"text": _PROMPT.format(explanation=text[:12000])}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, params={"key": settings.GEMINI_API_KEY}, json=payload)
    if resp.status_code != 200:
        print(f"[ai_extract] gemini HTTP {resp.status_code}: {resp.text[:300]}")
        return None
    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        return None
    parts = (candidates[0].get("content") or {}).get("parts") or []
    raw = "".join(p.get("text", "") for p in parts).strip()
    if not raw:
        return None
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else None


# ---------------------------------------------------------------------------
# Output normalisation
# ---------------------------------------------------------------------------

def _normalise(items: List[Any]) -> List[Dict[str, Any]]:
    """Coerce model output into clean source dicts the engine's
    parse_structured_sof() can consume."""
    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        source_type = str(it.get("source_type") or "other").strip().lower().replace(" ", "_")
        if source_type not in _ALLOWED_SOURCE_TYPES:
            source_type = "other"
        try:
            amount = float(it.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            # A source with no usable amount can't be matched against
            # bank evidence — skip it rather than emit a £0 claim.
            continue
        entry: Dict[str, Any] = {
            "source_type": source_type,
            "amount": amount,
            "currency": (str(it.get("currency") or "GBP").strip().upper() or "GBP"),
            "description": str(it.get("description") or "").strip(),
        }
        date = str(it.get("date") or "").strip()
        if date:
            # parse_structured_sof reads completion_date / distribution_date
            # for date-bearing source types; provide both generically.
            entry["completion_date"] = date
            entry["distribution_date"] = date
        out.append(entry)
    return out
