"""
Companies House Public Data API client (KYB — company due diligence).

Uses the free Companies House Public Data API:
    https://api.company-information.service.gov.uk

Authentication is HTTP Basic with the API key as the username and an
empty password. The key is read lazily from the COMPANIES_HOUSE_API_KEY
environment variable (Settings has extra="ignore", so a plain
os.environ read is deliberate — no Settings change required).

Degraded mode: when the key is unset every network method raises
ConfigurationError, which endpoints convert to a 409 with clear
guidance. The parsing helpers in this module are pure functions and
work without a key (they are unit-tested against real API shapes).

Rate limits: Companies House allows 600 requests per 5-minute window.
The client applies a small client-side courtesy delay between requests
and surfaces HTTP 429 as RateLimitError so endpoints can return a
clean 429 to the caller.

Regulatory notes embedded in responses (UK MLR 2017):
- reg 28(9): information from the PSC register alone is NOT
  verification of beneficial owners. PSC data is a cross-check;
  beneficial owners (>25%) must be verified individually (E-IDV).
- reg 30A: relevant persons MUST report material discrepancies between
  the PSC register and their own CDD findings to Companies House. The
  platform records the discrepancy and the fact of reporting; a human
  makes the report.
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional

import httpx

BASE_URL = "https://api.company-information.service.gov.uk"

API_KEY_ENV_VAR = "COMPANIES_HOUSE_API_KEY"

API_KEY_GUIDANCE = (
    "Companies House lookups are not configured. Set the "
    "COMPANIES_HOUSE_API_KEY environment variable — a free API key is "
    "available at developer.company-information.service.gov.uk "
    "(create an account, register an application, and copy the "
    "'Live' REST API key)."
)

# reg 28(9) — persistent compliance note returned with every KYB payload.
REG_28_9_NOTE = (
    "MLR 2017 reg 28(9): the PSC register alone is NOT verification of "
    "beneficial owners. Use PSC data as a cross-check only — each "
    "beneficial owner holding more than 25% must be identified and "
    "verified individually (see E-IDV)."
)

# reg 30A — returned when a PSC discrepancy is recorded.
REG_30A_NOTE = (
    "MLR 2017 reg 30A: the firm MUST report material discrepancies "
    "between its CDD findings and the Companies House PSC register to "
    "Companies House (via the 'Report a discrepancy about a beneficial "
    "owner on the PSC register' service). This platform records the "
    "discrepancy and your confirmation of reporting — the report itself "
    "must be made by a person at the firm."
)


class CompaniesHouseError(Exception):
    """Base class for Companies House client errors."""


class ConfigurationError(CompaniesHouseError):
    """Raised when a required API key is missing/invalid. Endpoints
    convert this to HTTP 409 with setup guidance."""


class RateLimitError(CompaniesHouseError):
    """Raised on HTTP 429 from Companies House (600 req / 5 min)."""


class CompaniesHouseAPIError(CompaniesHouseError):
    """Any other non-success response from the API."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


class CompaniesHouseClient:
    """Thin synchronous client for the Companies House Public Data API."""

    # Courtesy delay between consecutive requests (well inside the
    # 600/5min = 2 req/sec sustained budget).
    MIN_REQUEST_INTERVAL_SECONDS = 0.5

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = BASE_URL,
        transport: Optional[httpx.BaseTransport] = None,
        timeout: float = 15.0,
    ):
        # Lazy: fall back to the environment at call time, not import time.
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout
        self._last_request_at: float = 0.0

    # -- configuration ------------------------------------------------

    def _resolve_key(self) -> str:
        key = self._api_key or os.environ.get(API_KEY_ENV_VAR, "").strip()
        if not key:
            raise ConfigurationError(API_KEY_GUIDANCE)
        return key

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key or os.environ.get(API_KEY_ENV_VAR, "").strip())

    # -- transport ----------------------------------------------------

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self.MIN_REQUEST_INTERVAL_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        key = self._resolve_key()
        self._throttle()
        try:
            with httpx.Client(
                base_url=self._base_url,
                auth=(key, ""),
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise CompaniesHouseAPIError(0, f"Companies House request failed: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitError(
                "Companies House rate limit reached (600 requests per "
                "5 minutes). Please wait a few minutes and try again."
            )
        if response.status_code in (401, 403):
            raise ConfigurationError(
                "Companies House rejected the API key (HTTP "
                f"{response.status_code}). Check COMPANIES_HOUSE_API_KEY — "
                "a free key is available at "
                "developer.company-information.service.gov.uk."
            )
        if response.status_code == 404:
            raise CompaniesHouseAPIError(404, "Not found at Companies House.")
        if response.status_code >= 400:
            raise CompaniesHouseAPIError(
                response.status_code,
                f"Companies House returned HTTP {response.status_code}.",
            )
        return response.json()

    # -- public API ---------------------------------------------------

    def search_companies(self, q: str, items_per_page: int = 20) -> Dict[str, Any]:
        """GET /search/companies — company name/number search."""
        return self._get(
            "/search/companies",
            params={"q": q, "items_per_page": items_per_page},
        )

    def get_company(self, company_number: str) -> Dict[str, Any]:
        """GET /company/{number} — company profile."""
        return self._get(f"/company/{normalise_company_number(company_number)}")

    def get_officers(self, company_number: str) -> Dict[str, Any]:
        """GET /company/{number}/officers."""
        return self._get(
            f"/company/{normalise_company_number(company_number)}/officers",
            params={"items_per_page": 100},
        )

    def get_pscs(self, company_number: str) -> Dict[str, Any]:
        """GET /company/{number}/persons-with-significant-control."""
        try:
            return self._get(
                f"/company/{normalise_company_number(company_number)}/persons-with-significant-control",
                params={"items_per_page": 100},
            )
        except CompaniesHouseAPIError as exc:
            # Companies with no PSC data return 404 on this resource —
            # normalise to an empty list rather than an error.
            if exc.status_code == 404:
                return {"items": [], "active_count": 0, "ceased_count": 0, "total_results": 0}
            raise


# Module-level factory — endpoints call this so tests can monkeypatch it.
def get_client() -> CompaniesHouseClient:
    return CompaniesHouseClient()


# ---------------------------------------------------------------------------
# Pure parsing helpers (unit-testable, no network)
# ---------------------------------------------------------------------------

# Real natures_of_control identifiers from the Companies House PSC API.
NATURE_OF_CONTROL_LABELS: Dict[str, str] = {
    "ownership-of-shares-25-to-50-percent": "Owns 25–50% of shares",
    "ownership-of-shares-50-to-75-percent": "Owns 50–75% of shares",
    "ownership-of-shares-75-to-100-percent": "Owns 75–100% of shares",
    "voting-rights-25-to-50-percent": "Holds 25–50% of voting rights",
    "voting-rights-50-to-75-percent": "Holds 50–75% of voting rights",
    "voting-rights-75-to-100-percent": "Holds 75–100% of voting rights",
    "right-to-appoint-and-remove-directors": "Right to appoint or remove a majority of directors",
    "significant-influence-or-control": "Significant influence or control",
}

_OWNERSHIP_BAND_RE = re.compile(
    r"^ownership-of-shares-(\d+)-to-(\d+)-percent(?:-.*)?$"
)
_VOTING_BAND_RE = re.compile(r"^voting-rights-(\d+)-to-(\d+)-percent(?:-.*)?$")


def describe_nature_of_control(nature: str) -> str:
    """Human-readable label for a single natures_of_control identifier.

    Falls back to un-hyphenating unknown identifiers (the API also has
    trust/firm variants like 'ownership-of-shares-75-to-100-percent-as-trust').
    """
    if nature in NATURE_OF_CONTROL_LABELS:
        return NATURE_OF_CONTROL_LABELS[nature]
    m = _OWNERSHIP_BAND_RE.match(nature)
    if m:
        return f"Owns {m.group(1)}–{m.group(2)}% of shares ({nature.replace('-', ' ')})"
    return nature.replace("-", " ").capitalize()


def describe_natures_of_control(natures: Optional[List[str]]) -> List[str]:
    return [describe_nature_of_control(n) for n in (natures or [])]


def ownership_band(natures: Optional[List[str]]) -> Optional[str]:
    """Best shareholding band ('25–50%', '50–75%', '75–100%') from
    natures_of_control, preferring share ownership over voting rights.
    Returns None when no percentage band is stated."""
    best: Optional[tuple] = None  # (is_shares, low, high)
    for nature in natures or []:
        for regex, is_shares in ((_OWNERSHIP_BAND_RE, True), (_VOTING_BAND_RE, False)):
            m = regex.match(nature)
            if m:
                candidate = (is_shares, int(m.group(1)), int(m.group(2)))
                if best is None or candidate > best:
                    best = candidate
    if best is None:
        return None
    return f"{best[1]}–{best[2]}%"


def _address_to_str(address: Optional[Dict[str, Any]]) -> Optional[str]:
    if not address:
        return None
    parts = [
        address.get("premises"),
        address.get("address_line_1"),
        address.get("address_line_2"),
        address.get("locality"),
        address.get("region"),
        address.get("postal_code"),
        address.get("country"),
    ]
    joined = ", ".join(p for p in parts if p)
    return joined or None


def summarise_search_results(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Trim GET /search/companies to what the UI needs."""
    items = []
    for item in raw.get("items", []) or []:
        items.append(
            {
                "company_number": item.get("company_number"),
                "title": item.get("title"),
                "company_status": item.get("company_status"),
                "company_type": item.get("company_type"),
                "date_of_creation": item.get("date_of_creation"),
                "address_snippet": item.get("address_snippet"),
            }
        )
    return {
        "total_results": raw.get("total_results", len(items)),
        "items": items,
    }


def summarise_profile(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Trim GET /company/{number} to the fields we persist and display."""
    accounts = raw.get("accounts") or {}
    conf = raw.get("confirmation_statement") or {}
    return {
        "company_number": raw.get("company_number"),
        "company_name": raw.get("company_name"),
        "company_status": raw.get("company_status"),
        "company_status_detail": raw.get("company_status_detail"),
        "type": raw.get("type"),
        "jurisdiction": raw.get("jurisdiction"),
        "date_of_creation": raw.get("date_of_creation"),
        "date_of_cessation": raw.get("date_of_cessation"),
        "sic_codes": raw.get("sic_codes") or [],
        "registered_office_address": _address_to_str(raw.get("registered_office_address")),
        "registered_office_is_in_dispute": raw.get("registered_office_is_in_dispute"),
        "has_insolvency_history": raw.get("has_insolvency_history"),
        "has_charges": raw.get("has_charges"),
        "undeliverable_registered_office_address": raw.get(
            "undeliverable_registered_office_address"
        ),
        "accounts_overdue": accounts.get("overdue"),
        "confirmation_statement_overdue": conf.get("overdue"),
    }


def summarise_officers(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Trim GET /company/{number}/officers."""
    items = []
    for officer in raw.get("items", []) or []:
        dob = officer.get("date_of_birth") or {}
        items.append(
            {
                "name": officer.get("name"),
                "officer_role": officer.get("officer_role"),
                "appointed_on": officer.get("appointed_on"),
                "resigned_on": officer.get("resigned_on"),
                "nationality": officer.get("nationality"),
                "occupation": officer.get("occupation"),
                "country_of_residence": officer.get("country_of_residence"),
                # The public API deliberately only exposes month/year.
                "date_of_birth": (
                    f"{dob.get('month'):02d}/{dob.get('year')}"
                    if dob.get("month") and dob.get("year")
                    else None
                ),
                "address": _address_to_str(officer.get("address")),
            }
        )
    return {
        "active_count": raw.get("active_count", 0),
        "resigned_count": raw.get("resigned_count", 0),
        "total_results": raw.get("total_results", len(items)),
        "items": items,
    }


def summarise_pscs(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Trim GET /company/{number}/persons-with-significant-control.

    Each PSC gets human-readable natures_of_control descriptions plus
    an ownership_band, and a requires_individual_verification hint —
    the reg 28(9) point that the register is a cross-check, not
    verification.
    """
    items = []
    for psc in raw.get("items", []) or []:
        dob = psc.get("date_of_birth") or {}
        kind = psc.get("kind") or ""
        natures = psc.get("natures_of_control") or []
        is_individual = kind.startswith("individual-person")
        items.append(
            {
                "name": psc.get("name"),
                "kind": kind,
                "is_individual": is_individual,
                "natures_of_control": natures,
                "natures_described": describe_natures_of_control(natures),
                "ownership_band": ownership_band(natures),
                "notified_on": psc.get("notified_on"),
                "ceased_on": psc.get("ceased_on"),
                "nationality": psc.get("nationality"),
                "country_of_residence": psc.get("country_of_residence"),
                "date_of_birth": (
                    f"{dob.get('month'):02d}/{dob.get('year')}"
                    if dob.get("month") and dob.get("year")
                    else None
                ),
                "address": _address_to_str(psc.get("address")),
                # Corporate PSCs (kind corporate-entity-*) point at another
                # company — the identification obligation flows through to
                # the individuals behind it.
                "identification": psc.get("identification"),
                # reg 28(9): individuals on the register still need
                # individual identity verification (E-IDV) when active.
                "requires_individual_verification": is_individual and not psc.get("ceased_on"),
            }
        )
    return {
        "active_count": raw.get("active_count", 0),
        "ceased_count": raw.get("ceased_count", 0),
        "total_results": raw.get("total_results", len(items)),
        "items": items,
    }


def normalise_company_number(company_number: str) -> str:
    """Companies House numbers are 8 chars; numeric ones are zero-padded
    (e.g. '312919' -> '00312919'). Prefixed numbers (SC/NI/OC…) pass
    through upper-cased."""
    value = (company_number or "").strip().upper().replace(" ", "")
    if value.isdigit() and len(value) < 8:
        value = value.zfill(8)
    return value
