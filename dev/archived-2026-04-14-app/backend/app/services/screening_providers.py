"""
Screening provider adapters.

A ScreeningProvider normalises third-party (or local) screening results
into a common hit shape so the endpoints and the UI never care where a
hit came from:

    {source, external_ref, name, entity_type,
     categories: [sanctions|pep|adverse_media], score, raw}

Providers:
- LocalUKListProvider — wraps the local UK Sanctions List matcher; always
  available (sanctions screening is strict-liability, so this baseline
  runs for every party regardless of matter risk).
- DilisenseProvider   — commercial PEP/sanctions/adverse-media API;
  active only when DILISENSE_API_KEY is set in the environment.

CompositeScreener runs every active provider and aggregates hits.
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import httpx

from app.services.sanctions_screening import screen_name

logger = logging.getLogger(__name__)

DILISENSE_API_KEY_ENV = "DILISENSE_API_KEY"
DILISENSE_BASE_URL = os.environ.get("DILISENSE_BASE_URL", "https://api.dilisense.com/v1")


@dataclass
class ProviderHit:
    """A normalised screening hit."""
    source: str
    external_ref: Optional[str]
    name: str
    entity_type: Optional[str]
    categories: list = field(default_factory=list)  # sanctions | pep | adverse_media
    score: int = 0
    raw: dict = field(default_factory=dict)


class ScreeningProvider(ABC):
    """Interface every screening source implements."""

    name: str = "provider"

    def is_active(self) -> bool:
        return True

    @abstractmethod
    def screen(
        self,
        name: str,
        dob: Optional[date] = None,
        entity_type: Optional[str] = None,
    ) -> list[ProviderHit]:
        """Return normalised hits for the subject."""


class LocalUKListProvider(ScreeningProvider):
    """Local matcher over the imported UK Sanctions List (FCDO)."""

    name = "uk_fcdo_local"

    def __init__(self, db):
        self._db = db

    def screen(self, name, dob=None, entity_type=None):
        candidates = screen_name(name, dob=dob, entity_type=entity_type, db=self._db)
        hits = []
        for c in candidates:
            hits.append(ProviderHit(
                source="uk_fcdo",
                external_ref=c.external_id,
                name=c.matched_name,
                entity_type=c.entity_type,
                categories=["sanctions"],
                score=c.score,
                raw={
                    "matched_alias": c.matched_alias,
                    "dob_note": c.dob_note,
                    "regimes": c.regimes,
                    **(c.raw or {}),
                },
            ))
        return hits


class DilisenseProvider(ScreeningProvider):
    """dilisense PEP / sanctions / criminal-list API.

    Inactive unless DILISENSE_API_KEY is set. Network or API errors are
    logged and yield no hits — the local UK-list provider still runs, so
    a vendor outage never blocks the strict-liability baseline check.
    """

    name = "dilisense"
    # dilisense does not return a match score; hits it returns are already
    # filtered server-side, so we record a fixed high indicative score.
    DEFAULT_SCORE = 85

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0):
        self._api_key = api_key if api_key is not None else os.environ.get(DILISENSE_API_KEY_ENV)
        self._timeout = timeout

    def is_active(self) -> bool:
        return bool(self._api_key)

    @staticmethod
    def _categories_for(record: dict) -> list:
        source_type = str(record.get("source_type") or "").upper()
        categories = []
        if "SANCTION" in source_type:
            categories.append("sanctions")
        if "PEP" in source_type:
            categories.append("pep")
        if "CRIMINAL" in source_type or not categories:
            categories.append("adverse_media")
        return categories

    def screen(self, name, dob=None, entity_type=None):
        if not self.is_active():
            return []
        endpoint = (
            "checkEntity"
            if (entity_type or "").lower() in ("entity", "ship")
            else "checkIndividual"
        )
        params: dict = {"names": name}
        if dob is not None and endpoint == "checkIndividual":
            params["dob"] = dob.strftime("%d/%m/%Y")
        try:
            response = httpx.get(
                f"{DILISENSE_BASE_URL}/{endpoint}",
                params=params,
                headers={"x-api-key": self._api_key},
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 — vendor outage must not block screening
            logger.warning("dilisense screening failed (%s): %s", endpoint, exc)
            return []

        hits = []
        for record in payload.get("found_records", []) or []:
            hits.append(ProviderHit(
                source="dilisense",
                external_ref=str(record.get("source_id") or record.get("id") or "") or None,
                name=record.get("name") or name,
                entity_type=(record.get("entity_type") or entity_type or "").lower() or None,
                categories=self._categories_for(record),
                score=self.DEFAULT_SCORE,
                raw=record,
            ))
        return hits


class CompositeScreener:
    """Runs all active providers and aggregates their hits."""

    def __init__(self, db, providers: Optional[list] = None):
        self.providers: list[ScreeningProvider] = (
            providers if providers is not None
            else [LocalUKListProvider(db), DilisenseProvider()]
        )

    def active_providers(self) -> list[ScreeningProvider]:
        return [p for p in self.providers if p.is_active()]

    def screen(
        self,
        name: str,
        dob: Optional[date] = None,
        entity_type: Optional[str] = None,
    ) -> tuple[list[ProviderHit], list[str]]:
        """Return (hits, provider names used)."""
        hits: list[ProviderHit] = []
        used: list[str] = []
        for provider in self.active_providers():
            used.append(provider.name)
            try:
                hits.extend(provider.screen(name, dob=dob, entity_type=entity_type))
            except Exception as exc:  # noqa: BLE001
                logger.error("screening provider %s raised: %s", provider.name, exc)
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits, used
