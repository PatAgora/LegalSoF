"""
E-IDV (Electronic Identity Verification) provider framework.

Provider-agnostic: the platform speaks one interface (EidvProvider);
concrete providers plug in behind it.

Providers implemented here:

- ManualEidvProvider — always available. Generates a checklist-driven
  manual verification: the solicitor records document type, number,
  expiry, likeness confirmation, and certified-copy details. Results
  are stored with method='manual' and are explicitly labelled as
  TRADITIONAL verification — manual verification does NOT constitute
  DIATF-certified digital identity verification (HMT guidance, Feb
  2026: only services certified under the UK Digital Identity and
  Attributes Trust Framework satisfy MLR 2017 reg 28(19)
  automatically; the manual route remains the traditional approach).

- ComplyCubeProvider — STUB shaped to the ComplyCube REST API
  (https://docs.complycube.com). Reads COMPLYCUBE_API_KEY lazily from
  the environment; inactive when unset (methods raise
  ConfigurationError with setup guidance). The request/response shape
  matters more than live calls — a live contract is a later step.

The ConfigurationError raised here is the same class the Companies
House client uses, so endpoints convert missing-key situations to a
409 with guidance in a single place.
"""
from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from app.services.companies_house import ConfigurationError

COMPLYCUBE_API_KEY_ENV_VAR = "COMPLYCUBE_API_KEY"

COMPLYCUBE_GUIDANCE = (
    "ComplyCube E-IDV is not configured. Set the COMPLYCUBE_API_KEY "
    "environment variable (keys are issued at complycube.com once a "
    "contract is in place), or use provider='manual' for traditional "
    "solicitor-led verification."
)

# Displayed wherever a manual verification is created or completed.
MANUAL_METHOD_CAVEAT = (
    "Manual (traditional) verification — this does NOT constitute "
    "DIATF-certified electronic identity verification. Under HM "
    "Treasury guidance (Feb 2026), only digital identity services "
    "certified under the UK Digital Identity and Attributes Trust "
    "Framework satisfy MLR 2017 reg 28(19) automatically. Manual "
    "document checks remain the traditional route and must be "
    "performed and evidenced by the solicitor."
)

# The structured checklist a solicitor completes for a manual check.
MANUAL_CHECKLIST: List[Dict[str, Any]] = [
    {
        "id": "document_type",
        "label": "Identity document type",
        "description": (
            "Record the document inspected — e.g. passport, "
            "photocard driving licence, national identity card."
        ),
        "required": True,
    },
    {
        "id": "document_number",
        "label": "Document number",
        "description": "The unique number printed on the document.",
        "required": True,
    },
    {
        "id": "expiry_date",
        "label": "Document expiry date",
        "description": "Verify the document is current (DD/MM/YYYY).",
        "required": True,
    },
    {
        "id": "likeness_confirmed",
        "label": "Likeness confirmed",
        "description": (
            "Confirm the photograph is a true likeness of the person, "
            "checked in person or over live video."
        ),
        "required": True,
    },
    {
        "id": "certified_copy_details",
        "label": "Certified copy details (if not seen in person)",
        "description": (
            "If working from a certified copy: who certified it, their "
            "capacity, and the date of certification."
        ),
        "required": False,
    },
    {
        "id": "notes",
        "label": "Notes",
        "description": "Any further observations (e.g. name discrepancies, prior names).",
        "required": False,
    },
]


class EidvProviderError(Exception):
    """Base class for provider errors (other than configuration)."""


class EidvProvider(ABC):
    """Interface every E-IDV provider implements.

    create_verification(subject) -> {
        provider_ref: str,
        client_url: str | None,       # hosted-flow URL, if any
        instructions: dict | None,    # e.g. the manual checklist
    }
    get_result(provider_ref) -> {
        status: 'pending' | 'passed' | 'failed' | 'review',
        checks: {document, liveness, nfc_chip, address},  # per-check outcomes
        report: dict,                 # provider's full report payload
    }
    """

    name: str = "abstract"
    diatf_certified: bool = False

    @abstractmethod
    def create_verification(self, subject: Dict[str, Any]) -> Dict[str, Any]:
        """subject: {name, dob, email} (dob/email optional)."""

    @abstractmethod
    def get_result(self, provider_ref: str) -> Dict[str, Any]:
        ...


class ManualEidvProvider(EidvProvider):
    """Solicitor-led traditional verification. Always available.

    The 'provider' here is the human: create_verification issues the
    structured checklist; the result is recorded through the
    manual-result endpoint rather than polled from an API.
    """

    name = "manual"
    diatf_certified = False  # HMT Feb 2026: manual is NOT certified E-IDV

    def create_verification(self, subject: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "provider_ref": f"manual-{uuid.uuid4()}",
            "client_url": None,
            "instructions": {
                "caveat": MANUAL_METHOD_CAVEAT,
                "checklist": MANUAL_CHECKLIST,
                "subject": subject,
            },
        }

    def get_result(self, provider_ref: str) -> Dict[str, Any]:
        # Manual results are entered by the solicitor via the
        # manual-result endpoint; until then the check is pending.
        return {
            "status": "pending",
            "checks": {
                "document": "pending",
                "liveness": "pending",
                "nfc_chip": "not_applicable",
                "address": "pending",
            },
            "report": {"method": "manual", "caveat": MANUAL_METHOD_CAVEAT},
        }

    @staticmethod
    def build_result(
        document_type: str,
        document_number: str,
        expiry_date: str,
        likeness_confirmed: bool,
        certified_copy_details: Optional[str] = None,
        notes: Optional[str] = None,
        document_expired: bool = False,
    ) -> Dict[str, Any]:
        """Turn a completed manual checklist into the standard result
        shape. Pure function — unit-tested without a database.

        Outcome policy:
        - likeness not confirmed  -> failed
        - document expired        -> review (a human decides whether an
                                     expired document plus other evidence
                                     is acceptable)
        - otherwise               -> passed
        """
        if not likeness_confirmed:
            status = "failed"
        elif document_expired:
            status = "review"
        else:
            status = "passed"

        return {
            "status": status,
            "checks": {
                "document": "review" if document_expired else "passed",
                "liveness": "passed" if likeness_confirmed else "failed",
                "nfc_chip": "not_applicable",
                "address": "not_checked",
            },
            "report": {
                "method": "manual",
                "caveat": MANUAL_METHOD_CAVEAT,
                "document_type": document_type,
                "document_number": document_number,
                "expiry_date": expiry_date,
                "likeness_confirmed": likeness_confirmed,
                "certified_copy_details": certified_copy_details,
                "notes": notes,
            },
        }


class ComplyCubeProvider(EidvProvider):
    """ComplyCube stub, shaped to their REST API.

    Flow (per docs.complycube.com):
      1. POST /v1/clients            — create the client (person)
      2. POST /v1/flow/sessions      — hosted verification session
         (returns redirectUrl the subject completes on their device)
      3. GET  /v1/checks?clientId=…  — poll check outcomes

    Inactive when COMPLYCUBE_API_KEY is unset — methods raise
    ConfigurationError with guidance rather than attempting calls.
    """

    name = "complycube"
    diatf_certified = True  # applies once a certified contract is live
    BASE_URL = "https://api.complycube.com/v1"

    def __init__(self, api_key: Optional[str] = None, transport: Optional[httpx.BaseTransport] = None):
        self._api_key = api_key
        self._transport = transport

    def _resolve_key(self) -> str:
        key = self._api_key or os.environ.get(COMPLYCUBE_API_KEY_ENV_VAR, "").strip()
        if not key:
            raise ConfigurationError(COMPLYCUBE_GUIDANCE)
        return key

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key or os.environ.get(COMPLYCUBE_API_KEY_ENV_VAR, "").strip())

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.BASE_URL,
            headers={"Authorization": self._resolve_key(), "Content-Type": "application/json"},
            timeout=20.0,
            transport=self._transport,
        )

    def create_verification(self, subject: Dict[str, Any]) -> Dict[str, Any]:
        self._resolve_key()  # raises ConfigurationError when unset

        full_name = (subject.get("name") or "").strip()
        first, _, last = full_name.partition(" ")
        client_payload = {
            "type": "person",
            "email": subject.get("email"),
            "personDetails": {
                "firstName": first or full_name,
                "lastName": last or full_name,
                "dob": subject.get("dob"),
            },
        }
        with self._client() as http:
            client_resp = http.post("/clients", json=client_payload)
            client_resp.raise_for_status()
            client_id = client_resp.json()["id"]

            session_resp = http.post(
                "/flow/sessions",
                json={
                    "clientId": client_id,
                    "checkTypes": [
                        "standard_screening_check",
                        "identity_check",
                        "document_check",
                    ],
                },
            )
            session_resp.raise_for_status()
            session = session_resp.json()

        return {
            "provider_ref": client_id,
            "client_url": session.get("redirectUrl"),
            "instructions": None,
        }

    def get_result(self, provider_ref: str) -> Dict[str, Any]:
        self._resolve_key()  # raises ConfigurationError when unset

        with self._client() as http:
            resp = http.get("/checks", params={"clientId": provider_ref})
            resp.raise_for_status()
            checks = resp.json().get("items", [])

        outcomes: Dict[str, str] = {
            "document": "pending",
            "liveness": "pending",
            "nfc_chip": "pending",
            "address": "pending",
        }
        type_map = {
            "document_check": "document",
            "identity_check": "liveness",
            "nfc_identity_check": "nfc_chip",
            "proof_of_address_check": "address",
        }
        for check in checks:
            slot = type_map.get(check.get("type"))
            if not slot:
                continue
            outcome = (check.get("result") or {}).get("outcome")
            if outcome == "clear":
                outcomes[slot] = "passed"
            elif outcome == "attention":
                outcomes[slot] = "review"
            elif outcome is not None:
                outcomes[slot] = "failed"

        settled = [v for v in outcomes.values() if v != "pending"]
        if not settled:
            status = "pending"
        elif "failed" in settled:
            status = "failed"
        elif "review" in settled:
            status = "review"
        elif "pending" in outcomes.values():
            status = "pending"
        else:
            status = "passed"

        return {"status": status, "checks": outcomes, "report": {"items": checks}}


_PROVIDERS = {
    ManualEidvProvider.name: ManualEidvProvider,
    ComplyCubeProvider.name: ComplyCubeProvider,
}


def get_provider(name: str) -> EidvProvider:
    """Provider factory. Raises ValueError for unknown names."""
    cls = _PROVIDERS.get((name or "").strip().lower())
    if cls is None:
        raise ValueError(
            f"Unknown E-IDV provider '{name}'. Available: {', '.join(sorted(_PROVIDERS))}."
        )
    return cls()
