"""
Tests for KYB (Companies House) and the E-IDV framework.

Covers:
- Companies House response parsing against faithful inline fixtures
  (shapes follow the public data API:
  developer-specs.company-information.service.gov.uk).
- Client behaviour: missing key -> ConfigurationError, 429 ->
  RateLimitError, invalid key -> ConfigurationError, PSC 404 -> empty.
- Endpoint flows via TestClient + in-memory SQLite: KYB check
  creation, PSC-discrepancy (reg 30A) flow, manual E-IDV completion
  validation, ComplyCube-unconfigured 409.

Run with: pytest tests/test_kyb_eidv.py -v
"""
import os
import sys
from datetime import date, timedelta

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import companies_house
from app.services.companies_house import (
    API_KEY_ENV_VAR,
    CompaniesHouseClient,
    ConfigurationError,
    RateLimitError,
    describe_natures_of_control,
    normalise_company_number,
    ownership_band,
    summarise_officers,
    summarise_profile,
    summarise_pscs,
    summarise_search_results,
)
from app.services.eidv_providers import (
    COMPLYCUBE_API_KEY_ENV_VAR,
    MANUAL_CHECKLIST,
    MANUAL_METHOD_CAVEAT,
    ComplyCubeProvider,
    ManualEidvProvider,
    get_provider,
)


# ---------------------------------------------------------------------------
# Fixtures — faithful Companies House Public Data API shapes
# ---------------------------------------------------------------------------

SEARCH_FIXTURE = {
    "kind": "search#companies",
    "total_results": 1,
    "items_per_page": 20,
    "start_index": 0,
    "items": [
        {
            "kind": "searchresults#company",
            "title": "EXAMPLE TRADING LIMITED",
            "company_number": "01234567",
            "company_status": "active",
            "company_type": "ltd",
            "date_of_creation": "2001-05-14",
            "address_snippet": "1 High Street, Cardiff, CF10 1AA",
            "description": "01234567 - Incorporated on 14 May 2001",
            "links": {"self": "/company/01234567"},
        }
    ],
}

PROFILE_FIXTURE = {
    "company_name": "EXAMPLE TRADING LIMITED",
    "company_number": "01234567",
    "company_status": "active",
    "type": "ltd",
    "jurisdiction": "england-wales",
    "date_of_creation": "2001-05-14",
    "sic_codes": ["62020", "62090"],
    "registered_office_address": {
        "address_line_1": "1 High Street",
        "locality": "Cardiff",
        "postal_code": "CF10 1AA",
        "country": "Wales",
    },
    "registered_office_is_in_dispute": False,
    "undeliverable_registered_office_address": False,
    "has_insolvency_history": False,
    "has_charges": True,
    "accounts": {
        "next_due": "2026-12-31",
        "overdue": False,
        "last_accounts": {"made_up_to": "2025-03-31", "type": "small"},
    },
    "confirmation_statement": {"next_due": "2026-06-01", "overdue": False},
    "links": {
        "self": "/company/01234567",
        "officers": "/company/01234567/officers",
        "persons_with_significant_control": "/company/01234567/persons-with-significant-control",
    },
}

OFFICERS_FIXTURE = {
    "kind": "officer-list",
    "active_count": 2,
    "resigned_count": 1,
    "total_results": 3,
    "items": [
        {
            "name": "JONES, Angharad Mair",
            "officer_role": "director",
            "appointed_on": "2001-05-14",
            "nationality": "British",
            "occupation": "Company Director",
            "country_of_residence": "Wales",
            "date_of_birth": {"month": 3, "year": 1968},
            "address": {
                "premises": "1",
                "address_line_1": "High Street",
                "locality": "Cardiff",
                "postal_code": "CF10 1AA",
            },
            "links": {"officer": {"appointments": "/officers/abc123/appointments"}},
        },
        {
            "name": "DAVIES, Rhys",
            "officer_role": "secretary",
            "appointed_on": "2010-01-04",
            "resigned_on": "2020-09-30",
            "address": {"address_line_1": "2 Castle Road", "locality": "Swansea"},
        },
    ],
}

PSCS_FIXTURE = {
    "kind": "persons-with-significant-control#list",
    "active_count": 2,
    "ceased_count": 1,
    "total_results": 3,
    "items": [
        {
            "kind": "individual-person-with-significant-control",
            "name": "Mrs Angharad Mair Jones",
            "natures_of_control": [
                "ownership-of-shares-75-to-100-percent",
                "voting-rights-75-to-100-percent",
                "right-to-appoint-and-remove-directors",
            ],
            "notified_on": "2016-04-06",
            "nationality": "British",
            "country_of_residence": "Wales",
            "date_of_birth": {"month": 3, "year": 1968},
            "address": {
                "premises": "1",
                "address_line_1": "High Street",
                "locality": "Cardiff",
                "postal_code": "CF10 1AA",
            },
        },
        {
            "kind": "corporate-entity-person-with-significant-control",
            "name": "Holdco Investments Ltd",
            "natures_of_control": ["ownership-of-shares-25-to-50-percent"],
            "notified_on": "2018-02-01",
            "identification": {
                "legal_authority": "Companies Act 2006",
                "legal_form": "Private Limited Company",
                "place_registered": "England",
                "registration_number": "07654321",
            },
        },
        {
            "kind": "individual-person-with-significant-control",
            "name": "Mr Former Owner",
            "natures_of_control": ["ownership-of-shares-50-to-75-percent"],
            "notified_on": "2016-04-06",
            "ceased_on": "2018-02-01",
        },
    ],
}


# ---------------------------------------------------------------------------
# Parsing tests (pure functions, no network)
# ---------------------------------------------------------------------------

class TestParsing:
    def test_summarise_search_results(self):
        out = summarise_search_results(SEARCH_FIXTURE)
        assert out["total_results"] == 1
        item = out["items"][0]
        assert item["company_number"] == "01234567"
        assert item["title"] == "EXAMPLE TRADING LIMITED"
        assert item["company_status"] == "active"
        assert item["address_snippet"] == "1 High Street, Cardiff, CF10 1AA"

    def test_summarise_profile(self):
        out = summarise_profile(PROFILE_FIXTURE)
        assert out["company_name"] == "EXAMPLE TRADING LIMITED"
        assert out["company_number"] == "01234567"
        assert out["jurisdiction"] == "england-wales"
        assert out["sic_codes"] == ["62020", "62090"]
        assert out["registered_office_address"] == "1 High Street, Cardiff, CF10 1AA, Wales"
        assert out["has_charges"] is True
        assert out["has_insolvency_history"] is False
        assert out["accounts_overdue"] is False
        assert out["confirmation_statement_overdue"] is False

    def test_summarise_officers(self):
        out = summarise_officers(OFFICERS_FIXTURE)
        assert out["active_count"] == 2
        assert out["resigned_count"] == 1
        director = out["items"][0]
        assert director["name"] == "JONES, Angharad Mair"
        assert director["officer_role"] == "director"
        # Public API only exposes month/year of DOB.
        assert director["date_of_birth"] == "03/1968"
        secretary = out["items"][1]
        assert secretary["resigned_on"] == "2020-09-30"
        assert secretary["date_of_birth"] is None

    def test_summarise_pscs(self):
        out = summarise_pscs(PSCS_FIXTURE)
        assert out["active_count"] == 2
        individual = out["items"][0]
        assert individual["is_individual"] is True
        assert individual["ownership_band"] == "75–100%"
        assert "Owns 75–100% of shares" in individual["natures_described"]
        # reg 28(9): active individual PSCs need individual verification.
        assert individual["requires_individual_verification"] is True

        corporate = out["items"][1]
        assert corporate["is_individual"] is False
        assert corporate["requires_individual_verification"] is False
        assert corporate["identification"]["registration_number"] == "07654321"

        ceased = out["items"][2]
        assert ceased["ceased_on"] == "2018-02-01"
        assert ceased["requires_individual_verification"] is False

    def test_ownership_band_prefers_shares_and_highest(self):
        assert ownership_band(["voting-rights-25-to-50-percent"]) == "25–50%"
        assert ownership_band(
            ["voting-rights-75-to-100-percent", "ownership-of-shares-25-to-50-percent"]
        ) == "25–50%"  # share ownership preferred over voting rights
        assert ownership_band(["significant-influence-or-control"]) is None
        assert ownership_band(None) is None

    def test_describe_natures_handles_trust_variants(self):
        described = describe_natures_of_control(
            ["ownership-of-shares-75-to-100-percent-as-trust"]
        )
        assert "75–100%" in described[0]

    def test_normalise_company_number(self):
        assert normalise_company_number("312919") == "00312919"
        assert normalise_company_number("sc123456") == "SC123456"
        assert normalise_company_number(" 01234567 ") == "01234567"


# ---------------------------------------------------------------------------
# Client behaviour (httpx.MockTransport, no real network)
# ---------------------------------------------------------------------------

class TestCompaniesHouseClient:
    def test_missing_key_raises_configuration_error(self, monkeypatch):
        monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
        client = CompaniesHouseClient()
        with pytest.raises(ConfigurationError) as exc:
            client.search_companies("example")
        assert "COMPANIES_HOUSE_API_KEY" in str(exc.value)
        assert "developer.company-information.service.gov.uk" in str(exc.value)

    def test_search_parses_json(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=SEARCH_FIXTURE)
        )
        client = CompaniesHouseClient(api_key="test-key", transport=transport)
        raw = client.search_companies("example")
        assert raw["items"][0]["company_number"] == "01234567"

    def test_rate_limit_surfaces_cleanly(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(429))
        client = CompaniesHouseClient(api_key="test-key", transport=transport)
        with pytest.raises(RateLimitError):
            client.get_company("01234567")

    def test_invalid_key_raises_configuration_error(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(401))
        client = CompaniesHouseClient(api_key="bad-key", transport=transport)
        with pytest.raises(ConfigurationError):
            client.get_company("01234567")

    def test_pscs_404_normalised_to_empty(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(404))
        client = CompaniesHouseClient(api_key="test-key", transport=transport)
        out = client.get_pscs("01234567")
        assert out["items"] == []
        assert out["active_count"] == 0


# ---------------------------------------------------------------------------
# E-IDV providers (unit)
# ---------------------------------------------------------------------------

class TestEidvProviders:
    def test_manual_provider_issues_checklist(self):
        provider = get_provider("manual")
        assert isinstance(provider, ManualEidvProvider)
        assert provider.diatf_certified is False
        created = provider.create_verification({"name": "Angharad Jones"})
        assert created["provider_ref"].startswith("manual-")
        assert created["client_url"] is None
        assert created["instructions"]["checklist"] == MANUAL_CHECKLIST
        assert "DIATF" in created["instructions"]["caveat"]

    def test_manual_build_result_outcomes(self):
        passed = ManualEidvProvider.build_result(
            "passport", "123456789", "2030-01-01", likeness_confirmed=True
        )
        assert passed["status"] == "passed"
        assert passed["checks"]["liveness"] == "passed"
        assert passed["report"]["caveat"] == MANUAL_METHOD_CAVEAT

        failed = ManualEidvProvider.build_result(
            "passport", "123456789", "2030-01-01", likeness_confirmed=False
        )
        assert failed["status"] == "failed"

        review = ManualEidvProvider.build_result(
            "passport", "123456789", "2020-01-01",
            likeness_confirmed=True, document_expired=True,
        )
        assert review["status"] == "review"
        assert review["checks"]["document"] == "review"

    def test_complycube_unconfigured_raises(self, monkeypatch):
        monkeypatch.delenv(COMPLYCUBE_API_KEY_ENV_VAR, raising=False)
        provider = ComplyCubeProvider()
        assert provider.is_configured is False
        with pytest.raises(ConfigurationError) as exc:
            provider.create_verification({"name": "Angharad Jones"})
        assert "COMPLYCUBE_API_KEY" in str(exc.value)

    def test_unknown_provider_rejected(self):
        with pytest.raises(ValueError):
            get_provider("onfido")


# ---------------------------------------------------------------------------
# Endpoint flows — FastAPI TestClient + in-memory SQLite
# ---------------------------------------------------------------------------

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.models  # noqa: F401 — register all mappers
from app.models.audit import AuditLog
from app.models.eidv import EidvCheck  # noqa: F401
from app.models.kyb import KybCheck
from app.models.matter import Matter
from app.models.user import User, UserRole
from app.api.dependencies.auth import require_analyst
from app.api.v1.endpoints import eidv as eidv_endpoints
from app.api.v1.endpoints import kyb as kyb_endpoints
from app.db.session import get_sync_db


class FakeCompaniesHouseClient:
    """Canned responses shaped like the real client's raw JSON."""

    def search_companies(self, q, items_per_page=20):
        return SEARCH_FIXTURE

    def get_company(self, number):
        return PROFILE_FIXTURE

    def get_officers(self, number):
        return OFFICERS_FIXTURE

    def get_pscs(self, number):
        return PSCS_FIXTURE


@pytest.fixture()
def api(monkeypatch):
    """TestClient over the KYB + E-IDV routers with SQLite and a fake
    Companies House client."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    session = TestingSession()
    user = User(
        email="analyst@example.com",
        hashed_password="x",
        full_name="Test Analyst",
        role=UserRole.ADMIN,
        is_active=True,
        is_superuser=True,
    )
    session.add(user)
    session.flush()
    matter = Matter(
        reference_number="TEST-0001",
        client_name="Example Client",
        target_amount=500000,
        created_by_id=user.id,
    )
    session.add(matter)
    session.commit()
    user_id, matter_id = user.id, matter.id

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    def override_user():
        db = TestingSession()
        try:
            return db.query(User).get(user_id)
        finally:
            db.close()

    monkeypatch.setattr(
        kyb_endpoints.companies_house, "get_client", lambda: FakeCompaniesHouseClient()
    )

    app = FastAPI()
    app.include_router(kyb_endpoints.router, prefix="/api/v1")
    app.include_router(eidv_endpoints.router, prefix="/api/v1")
    app.dependency_overrides[get_sync_db] = override_db
    app.dependency_overrides[require_analyst] = override_user

    client = TestClient(app)
    client.matter_id = matter_id
    client.session_factory = TestingSession
    yield client
    session.close()
    engine.dispose()


class TestKybEndpoints:
    def test_search(self, api):
        r = api.get("/api/v1/kyb/search", params={"q": "example"})
        assert r.status_code == 200
        body = r.json()
        assert body["items"][0]["company_number"] == "01234567"
        assert "reg_28_9_note" in body
        assert "NOT verification" in body["reg_28_9_note"]

    def test_search_without_key_returns_409(self, api, monkeypatch):
        monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
        monkeypatch.setattr(
            kyb_endpoints.companies_house, "get_client", lambda: CompaniesHouseClient()
        )
        r = api.get("/api/v1/kyb/search", params={"q": "example"})
        assert r.status_code == 409
        assert "COMPANIES_HOUSE_API_KEY" in r.json()["detail"]

    def test_create_check_persists_snapshot_and_audit(self, api):
        r = api.post(
            f"/api/v1/matters/{api.matter_id}/kyb",
            json={"company_number": "1234567"},  # short number gets zero-padded
        )
        assert r.status_code == 201
        body = r.json()
        assert body["company_number"] == "01234567"
        assert body["company_name"] == "EXAMPLE TRADING LIMITED"
        assert body["status"] == "complete"
        assert body["pscs"]["items"][0]["ownership_band"] == "75–100%"
        assert "reg_28_9_note" in body

        db = api.session_factory()
        try:
            audit = (
                db.query(AuditLog)
                .filter(AuditLog.entity_type == "kyb_check", AuditLog.entity_id == body["id"])
                .all()
            )
            assert len(audit) == 1
            assert "KYB check run" in audit[0].description
        finally:
            db.close()

    def test_list_checks(self, api):
        api.post(f"/api/v1/matters/{api.matter_id}/kyb", json={"company_number": "01234567"})
        r = api.get(f"/api/v1/matters/{api.matter_id}/kyb")
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1

    def test_psc_discrepancy_flow(self, api):
        created = api.post(
            f"/api/v1/matters/{api.matter_id}/kyb", json={"company_number": "01234567"}
        ).json()
        check_id = created["id"]

        # Too short — reg 30A record needs substance.
        r = api.post(
            f"/api/v1/matters/{api.matter_id}/kyb/{check_id}/psc-discrepancy",
            json={"details": "too short"},
        )
        assert r.status_code == 422

        details = (
            "CDD identified Mr B Hidden as a 40% beneficial owner; he does not "
            "appear on the PSC register. Discrepancy reported to Companies House "
            "on 06/07/2026 by the MLRO."
        )
        r = api.post(
            f"/api/v1/matters/{api.matter_id}/kyb/{check_id}/psc-discrepancy",
            json={"details": details},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "discrepancy_reported"
        assert body["psc_discrepancy"] == details
        assert "reg 30A" in body["reg_30a_note"]

        # Refresh must NOT clear the recorded discrepancy status.
        r = api.post(f"/api/v1/matters/{api.matter_id}/kyb/{check_id}/refresh")
        assert r.status_code == 200
        assert r.json()["status"] == "discrepancy_reported"

        db = api.session_factory()
        try:
            stored = db.query(KybCheck).get(check_id)
            assert stored.psc_discrepancy_reported_at is not None
        finally:
            db.close()

    def test_missing_matter_404(self, api):
        r = api.post("/api/v1/matters/99999/kyb", json={"company_number": "01234567"})
        assert r.status_code == 404


class TestEidvEndpoints:
    def _start_manual(self, api, subject_type="client"):
        return api.post(
            f"/api/v1/matters/{api.matter_id}/eidv",
            json={
                "subject_type": subject_type,
                "subject_name": "Angharad Jones",
                "subject_dob": "1968-03-15",
                "provider": "manual",
            },
        )

    def test_start_manual_returns_checklist_and_caveat(self, api):
        r = self._start_manual(api, subject_type="beneficial_owner")
        assert r.status_code == 201
        body = r.json()
        assert body["provider"] == "manual"
        assert body["status"] == "pending"
        assert body["diatf_certified"] is False
        assert body["subject_type"] == "beneficial_owner"
        assert len(body["instructions"]["checklist"]) == len(MANUAL_CHECKLIST)
        assert "DIATF" in body["caveat"]

    def test_invalid_subject_type_rejected(self, api):
        r = api.post(
            f"/api/v1/matters/{api.matter_id}/eidv",
            json={"subject_type": "solicitor", "subject_name": "X Y", "provider": "manual"},
        )
        assert r.status_code == 422

    def test_complycube_unconfigured_409(self, api, monkeypatch):
        monkeypatch.delenv(COMPLYCUBE_API_KEY_ENV_VAR, raising=False)
        r = api.post(
            f"/api/v1/matters/{api.matter_id}/eidv",
            json={"subject_type": "client", "subject_name": "Angharad Jones", "provider": "complycube"},
        )
        assert r.status_code == 409
        assert "COMPLYCUBE_API_KEY" in r.json()["detail"]

    def test_manual_result_validation_and_completion(self, api):
        check_id = self._start_manual(api).json()["id"]
        url = f"/api/v1/matters/{api.matter_id}/eidv/{check_id}/manual-result"

        # Missing required fields → 422.
        r = api.put(url, json={"document_type": "passport"})
        assert r.status_code == 422

        # Bad expiry date format → 422.
        r = api.put(url, json={
            "document_type": "passport",
            "document_number": "123456789",
            "expiry_date": "31/12/2030",
            "likeness_confirmed": True,
        })
        assert r.status_code == 422

        # Valid completion → passed, never DIATF-certified.
        future = (date.today() + timedelta(days=365)).isoformat()
        r = api.put(url, json={
            "document_type": "passport",
            "document_number": "123456789",
            "expiry_date": future,
            "likeness_confirmed": True,
            "notes": "Seen in person at the office.",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "passed"
        assert body["diatf_certified"] is False
        assert body["method"] == "manual"
        assert body["completed_at"] is not None
        assert "DIATF" in body["caveat"]
        assert "Document type: passport" in body["evidence_notes"]

        # Double completion → 409.
        r = api.put(url, json={
            "document_type": "passport",
            "document_number": "123456789",
            "expiry_date": future,
            "likeness_confirmed": True,
        })
        assert r.status_code == 409

    def test_manual_result_expired_document_goes_to_review(self, api):
        check_id = self._start_manual(api).json()["id"]
        past = (date.today() - timedelta(days=30)).isoformat()
        r = api.put(
            f"/api/v1/matters/{api.matter_id}/eidv/{check_id}/manual-result",
            json={
                "document_type": "driving_licence",
                "document_number": "JONES903156AM9XY",
                "expiry_date": past,
                "likeness_confirmed": True,
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "review"

    def test_manual_result_likeness_not_confirmed_fails(self, api):
        check_id = self._start_manual(api).json()["id"]
        future = (date.today() + timedelta(days=365)).isoformat()
        r = api.put(
            f"/api/v1/matters/{api.matter_id}/eidv/{check_id}/manual-result",
            json={
                "document_type": "passport",
                "document_number": "123456789",
                "expiry_date": future,
                "likeness_confirmed": False,
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "failed"

    def test_list_checks_includes_caveat(self, api):
        self._start_manual(api)
        r = api.get(f"/api/v1/matters/{api.matter_id}/eidv")
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 1
        assert "DIATF" in body["manual_caveat"]
