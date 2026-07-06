"""
Sanctions screening service — UK Sanctions List parsing and name matching.

Stdlib-only fuzzy matching (unicodedata + difflib), fast enough for the
full UK Sanctions List (~6,300 designations) by pre-indexing entries on
their name tokens.

Sanctions screening is a STRICT-LIABILITY regime (SAMLA 2018): every party
is screened regardless of the matter's risk rating.

Public surface:
- parse_uk_sanctions_xml(content)      — parse the FCDO XML publication.
- normalize_name(name)                 — canonical form used for matching.
- SanctionsIndex                       — token-indexed matcher.
- screen_name(name, dob, entity_type)  — screen against the current dataset.
- derive_check_status(...)             — adjudication state transitions.
"""
from __future__ import annotations

import logging
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime
from difflib import SequenceMatcher, get_close_matches
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

DEFAULT_MATCH_THRESHOLD = 75

# Honorifics and titles stripped during normalisation. Kept deliberately
# conservative — only tokens that are unambiguous titles.
_TITLES = {
    "mr", "mrs", "ms", "miss", "mx", "dr", "prof", "professor", "sir",
    "dame", "lord", "lady", "baron", "baroness", "rev", "reverend",
    "hon", "honourable", "capt", "captain", "col", "colonel", "gen",
    "general", "maj", "major", "lt", "lieutenant", "sgt", "sergeant",
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def get_match_threshold() -> int:
    """Match threshold (0-100), configurable via SCREENING_MATCH_THRESHOLD."""
    try:
        return int(os.environ.get("SCREENING_MATCH_THRESHOLD", DEFAULT_MATCH_THRESHOLD))
    except ValueError:
        return DEFAULT_MATCH_THRESHOLD


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Casefold, transliterate accents, strip titles/punctuation, squash spaces."""
    if not name:
        return ""
    # NFKD + drop combining marks: José -> Jose, Đorđe -> Dorde (best effort).
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = stripped.casefold()
    no_punct = _PUNCT_RE.sub(" ", lowered)
    tokens = [t for t in _WS_RE.split(no_punct) if t]
    tokens = [t for t in tokens if t not in _TITLES]
    return " ".join(tokens)


def name_tokens(name: str) -> frozenset:
    return frozenset(normalize_name(name).split())


# ---------------------------------------------------------------------------
# UK Sanctions List XML parsing
# ---------------------------------------------------------------------------

def _parse_uk_date(value: Optional[str]) -> Optional[date]:
    """Parse DD/MM/YYYY. Returns None for blanks or placeholder parts."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def parse_dob_parts(value: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse an FCDO DOB string ('07/08/1957' or 'dd/mm/1957') to (d, m, y)."""
    parts = (value or "").strip().split("/")
    if len(parts) != 3:
        return (None, None, None)

    def _num(p: str) -> Optional[int]:
        p = p.strip()
        return int(p) if p.isdigit() else None

    return (_num(parts[0]), _num(parts[1]), _num(parts[2]))


def parse_uk_sanctions_xml(content: bytes) -> tuple[Optional[date], list[dict]]:
    """Parse the UK Sanctions List XML publication.

    Returns (date_generated, entries) where each entry is a dict with the
    fields of the sanctions_entries table. Raises ValueError on a document
    that is not a UK Sanctions List.
    """
    root = ET.fromstring(content)
    if root.tag != "Designations":
        raise ValueError(f"Unexpected root element {root.tag!r} — not a UK Sanctions List XML")

    date_generated = _parse_uk_date(root.findtext("DateGenerated"))
    entries: list[dict] = []

    for desig in root.findall("Designation"):
        external_id = (desig.findtext("UniqueID") or "").strip()
        if not external_id:
            continue

        raw_type = (desig.findtext("IndividualEntityShip") or "").strip().lower()
        entity_type = raw_type if raw_type in ("individual", "entity", "ship") else "entity"

        primary_name = ""
        aliases: list[str] = []
        names_el = desig.find("Names")
        if names_el is not None:
            for name_el in names_el.findall("Name"):
                # Name parts are Name1..Name6 in order (Name6 = surname/main).
                parts = [
                    (name_el.findtext(f"Name{i}") or "").strip()
                    for i in range(1, 7)
                ]
                full = " ".join(p for p in parts if p)
                if not full:
                    continue
                name_type = (name_el.findtext("NameType") or "").strip().lower()
                if name_type == "primary name" and not primary_name:
                    primary_name = full
                else:
                    aliases.append(full)
        if not primary_name:
            if aliases:
                primary_name = aliases.pop(0)
            else:
                continue  # unusable designation with no latin-script name

        dobs: list[str] = []
        nationalities: list[str] = []
        ind_details = desig.find("IndividualDetails")
        if ind_details is not None:
            for dob_el in ind_details.iter("DOB"):
                if dob_el.text and dob_el.text.strip():
                    dobs.append(dob_el.text.strip())
            for nat_el in ind_details.iter("Nationality"):
                if nat_el.text and nat_el.text.strip():
                    nationalities.append(nat_el.text.strip())

        regime = (desig.findtext("RegimeName") or "").strip()
        listed_on = _parse_uk_date(desig.findtext("DateDesignated"))

        entries.append({
            "source": "uk_fcdo",
            "external_id": external_id,
            "entity_type": entity_type,
            "primary_name": primary_name,
            "aliases": aliases,
            "dob": dobs[0] if dobs else None,
            "nationalities": nationalities,
            "regimes": [regime] if regime else [],
            "listed_on": listed_on,
            "raw": {
                "dobs": dobs,
                "un_reference": (desig.findtext("UNReferenceNumber") or "").strip() or None,
                "ofsi_group_id": (desig.findtext("OFSIGroupID") or "").strip() or None,
                "sanctions_imposed": (desig.findtext("SanctionsImposed") or "").strip() or None,
                "uk_statement_of_reasons": (desig.findtext("UKStatementofReasons") or "").strip() or None,
                "last_updated": (desig.findtext("LastUpdated") or "").strip() or None,
                "designation_source": (desig.findtext("DesignationSource") or "").strip() or None,
            },
        })

    return date_generated, entries


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

@dataclass
class MatchCandidate:
    """A scored candidate match against a sanctions entry."""
    entry_id: Optional[int]
    external_id: str
    matched_name: str
    entity_type: str
    score: int
    matched_alias: Optional[str] = None    # set when an alias (not primary) matched best
    dob_note: Optional[str] = None         # corroborated | contradicted | None
    regimes: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def _get(entry: Any, key: str, default=None):
    """Field access working for both dicts and ORM rows."""
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _name_similarity(q_norm: str, q_tokens: frozenset, c_norm: str, c_tokens: frozenset) -> float:
    """0.0-1.0 similarity of two normalised names."""
    if not q_norm or not c_norm:
        return 0.0
    if q_norm == c_norm:
        return 1.0
    r_full = SequenceMatcher(None, q_norm, c_norm).ratio()
    r_sorted = SequenceMatcher(
        None, " ".join(sorted(q_tokens)), " ".join(sorted(c_tokens))
    ).ratio()
    union = q_tokens | c_tokens
    jaccard = (len(q_tokens & c_tokens) / len(union)) if union else 0.0
    return max(r_full, r_sorted, jaccard)


class SanctionsIndex:
    """Token-indexed sanctions entries for fast candidate retrieval.

    Build once per dataset; screen() then only scores entries sharing at
    least one (fuzzy-expanded) token with the query.
    """

    def __init__(self, entries: Iterable[Any]):
        self._records: list[dict] = []
        self._token_postings: dict[str, set] = {}
        for entry in entries:
            names = [_get(entry, "primary_name") or ""]
            names += list(_get(entry, "aliases") or [])
            variants = []
            for n in names:
                norm = normalize_name(n)
                if norm:
                    variants.append((n, norm, frozenset(norm.split())))
            if not variants:
                continue
            raw = _get(entry, "raw") or {}
            dob_years, dob_full = self._extract_dobs(raw, _get(entry, "dob"))
            idx = len(self._records)
            self._records.append({
                "entry_id": _get(entry, "id"),
                "external_id": _get(entry, "external_id") or "",
                "entity_type": (_get(entry, "entity_type") or "").lower(),
                "primary_name": _get(entry, "primary_name") or "",
                "variants": variants,
                "dob_years": dob_years,
                "dob_full": dob_full,
                "regimes": list(_get(entry, "regimes") or []),
                "raw": raw,
            })
            for _, _, tokens in variants:
                for tok in tokens:
                    self._token_postings.setdefault(tok, set()).add(idx)
        self._vocab = list(self._token_postings.keys())

    @staticmethod
    def _extract_dobs(raw: dict, dob_field: Optional[str]) -> tuple[set, set]:
        """Return (years, full (d,m,y) tuples) from an entry's DOB strings."""
        dob_strings = list(raw.get("dobs") or [])
        if dob_field and dob_field not in dob_strings:
            dob_strings.append(dob_field)
        years: set = set()
        fulls: set = set()
        for s in dob_strings:
            d, m, y = parse_dob_parts(s)
            if y:
                years.add(y)
            if d and m and y:
                fulls.add((d, m, y))
        return years, fulls

    def __len__(self) -> int:
        return len(self._records)

    def _candidate_indices(self, q_tokens: frozenset) -> set:
        indices: set = set()
        for tok in q_tokens:
            postings = self._token_postings.get(tok)
            if postings:
                indices |= postings
            # Fuzzy token expansion catches typos/transliteration variants
            # (e.g. "khairulah" -> "khairullah").
            for close in get_close_matches(tok, self._vocab, n=5, cutoff=0.82):
                if close != tok:
                    indices |= self._token_postings.get(close, set())
        return indices

    def screen(
        self,
        name: str,
        dob: Optional[date] = None,
        entity_type: Optional[str] = None,
        threshold: Optional[int] = None,
    ) -> list[MatchCandidate]:
        """Return candidate matches scoring >= threshold, best first."""
        threshold = get_match_threshold() if threshold is None else threshold
        q_norm = normalize_name(name)
        if not q_norm:
            return []
        q_tokens = frozenset(q_norm.split())
        wanted_type = entity_type.lower() if entity_type else None

        results: list[MatchCandidate] = []
        for idx in self._candidate_indices(q_tokens):
            rec = self._records[idx]
            if wanted_type and rec["entity_type"] != wanted_type:
                continue

            best_sim = 0.0
            best_variant = None
            for original, c_norm, c_tokens in rec["variants"]:
                sim = _name_similarity(q_norm, q_tokens, c_norm, c_tokens)
                if sim > best_sim:
                    best_sim = sim
                    best_variant = original
            score = 100.0 * best_sim

            # DOB corroboration / contradiction.
            dob_note = None
            if dob is not None and (rec["dob_years"] or rec["dob_full"]):
                if (dob.day, dob.month, dob.year) in rec["dob_full"]:
                    score += 10
                    dob_note = "corroborated"
                elif dob.year in rec["dob_years"]:
                    score += 5
                    dob_note = "corroborated"
                else:
                    score -= 25
                    dob_note = "contradicted"

            score_int = max(0, min(100, round(score)))
            if score_int >= threshold:
                matched_alias = (
                    best_variant
                    if best_variant and best_variant != rec["primary_name"]
                    else None
                )
                results.append(MatchCandidate(
                    entry_id=rec["entry_id"],
                    external_id=rec["external_id"],
                    matched_name=rec["primary_name"],
                    entity_type=rec["entity_type"],
                    score=score_int,
                    matched_alias=matched_alias,
                    dob_note=dob_note,
                    regimes=rec["regimes"],
                    raw=rec["raw"],
                ))

        results.sort(key=lambda m: m.score, reverse=True)
        return results


# ---------------------------------------------------------------------------
# Dataset-backed screening (index cached per dataset)
# ---------------------------------------------------------------------------

_index_cache: dict = {"dataset_id": None, "index": None}


def get_latest_dataset(db):
    from app.models.screening import SanctionsDataset
    return (
        db.query(SanctionsDataset)
        .order_by(SanctionsDataset.imported_at.desc(), SanctionsDataset.id.desc())
        .first()
    )


def get_screening_index(db) -> tuple[Optional[Any], Optional[SanctionsIndex]]:
    """Return (latest dataset, SanctionsIndex) — index rebuilt on dataset change."""
    from app.models.screening import SanctionsEntry

    dataset = get_latest_dataset(db)
    if dataset is None:
        return None, None
    if _index_cache["dataset_id"] != dataset.id or _index_cache["index"] is None:
        entries = (
            db.query(SanctionsEntry)
            .filter(SanctionsEntry.dataset_id == dataset.id)
            .all()
        )
        logger.info("Building sanctions index: dataset %s, %d entries", dataset.version, len(entries))
        _index_cache["index"] = SanctionsIndex(entries)
        _index_cache["dataset_id"] = dataset.id
    return dataset, _index_cache["index"]


def invalidate_index_cache() -> None:
    _index_cache["dataset_id"] = None
    _index_cache["index"] = None


def screen_name(
    name: str,
    dob: Optional[date] = None,
    entity_type: Optional[str] = None,
    threshold: Optional[int] = None,
    db=None,
) -> list[MatchCandidate]:
    """Screen a name against the current UK Sanctions List dataset.

    Opens (and closes) its own session when `db` is not supplied, so it is
    directly callable in-process outside a request.
    """
    own_session = db is None
    if own_session:
        from app.db.session import get_sync_session
        db = get_sync_session()()
    try:
        dataset, index = get_screening_index(db)
        if index is None:
            logger.warning("screen_name called but no sanctions dataset is imported")
            return []
        return index.screen(name, dob=dob, entity_type=entity_type, threshold=threshold)
    finally:
        if own_session:
            db.close()


# ---------------------------------------------------------------------------
# Adjudication state transitions
# ---------------------------------------------------------------------------

def derive_check_status(adjudication_statuses: Iterable[str]) -> str:
    """Derive a check's status from its hits' adjudication statuses.

    - no hits                          -> clear
    - ANY true_match                   -> confirmed_match (sanctions freeze)
    - ALL adjudicated false_positive   -> clear
    - otherwise (pending remain)       -> potential_match
    """
    statuses = [
        s.value if hasattr(s, "value") else str(s)
        for s in adjudication_statuses
    ]
    if not statuses:
        return "clear"
    if any(s == "true_match" for s in statuses):
        return "confirmed_match"
    if all(s == "false_positive" for s in statuses):
        return "clear"
    return "potential_match"
