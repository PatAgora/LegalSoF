"""
Unit tests for the PEP/sanctions screening module.

Covers: name matching (exact, alias, token order, accents, titles, DOB
corroboration/contradiction, threshold), the UK Sanctions List XML parser
(inline fixture — no network), and adjudication state transitions
(pure function + ORM flow on in-memory SQLite).

Run with: pytest tests/test_screening.py -v
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.sanctions_screening import (  # noqa: E402
    SanctionsIndex,
    derive_check_status,
    normalize_name,
    parse_dob_parts,
    parse_uk_sanctions_xml,
)


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

# Mirrors the real UK Sanctions List schema (validated against the live
# publication of 06/07/2026 from sanctionslist.fcdo.gov.uk).
FIXTURE_XML = """<?xml version="1.0" encoding="utf-8"?>
<Designations xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <DateGenerated>06/07/2026</DateGenerated>
  <Designation>
    <LastUpdated>14/04/2026</LastUpdated>
    <DateDesignated>25/01/2001</DateDesignated>
    <UniqueID>AFG0006</UniqueID>
    <OFSIGroupID>7172</OFSIGroupID>
    <UNReferenceNumber>TAi.002</UNReferenceNumber>
    <Names>
      <Name>
        <Name1>MOHAMMAD</Name1>
        <Name2>HASSAN</Name2>
        <Name6>AKHUND</Name6>
        <NameType>Primary Name</NameType>
      </Name>
      <Name>
        <Name6>Mullah Hassan Akhund</Name6>
        <NameType>Alias</NameType>
      </Name>
    </Names>
    <Titles>
      <Title>Mullah</Title>
    </Titles>
    <RegimeName>The Afghanistan (Sanctions) (EU Exit) Regulations 2020</RegimeName>
    <IndividualEntityShip>Individual</IndividualEntityShip>
    <DesignationSource>UN</DesignationSource>
    <SanctionsImposed>Asset freeze|Travel Ban</SanctionsImposed>
    <UKStatementofReasons>Member of the Taliban leadership.</UKStatementofReasons>
    <IndividualDetails>
      <Individual>
        <DOBs>
          <DOB>dd/mm/1957</DOB>
          <DOB>02/03/1958</DOB>
        </DOBs>
        <Nationalities>
          <Nationality>Afghanistan</Nationality>
        </Nationalities>
      </Individual>
    </IndividualDetails>
  </Designation>
  <Designation>
    <LastUpdated>16/04/2026</LastUpdated>
    <DateDesignated>29/06/2012</DateDesignated>
    <UniqueID>AFG0001</UniqueID>
    <Names>
      <Name>
        <Name6>HAJI KHAIRULLAH HAJI SATTAR MONEY EXCHANGE</Name6>
        <NameType>Primary Name</NameType>
      </Name>
      <Name>
        <Name6>Haji Khairullah Money Exchange</Name6>
        <NameType>Alias</NameType>
      </Name>
    </Names>
    <RegimeName>The Afghanistan (Sanctions) (EU Exit) Regulations 2020</RegimeName>
    <IndividualEntityShip>Entity</IndividualEntityShip>
    <SanctionsImposed>Asset freeze</SanctionsImposed>
    <UKStatementofReasons>Provided financial services to the Taliban.</UKStatementofReasons>
  </Designation>
</Designations>
"""


def make_index():
    _, entries = parse_uk_sanctions_xml(FIXTURE_XML.encode("utf-8"))
    # Give dict entries synthetic ids like ORM rows would have.
    for i, e in enumerate(entries, start=1):
        e["id"] = i
    extra = {
        "id": 99,
        "external_id": "RUS0001",
        "entity_type": "individual",
        "primary_name": "José García Fernández",
        "aliases": ["Pepe Garcia"],
        "dob": "15/06/1970",
        "nationalities": ["Spain"],
        "regimes": ["Test Regime"],
        "raw": {"dobs": ["15/06/1970"]},
    }
    return SanctionsIndex(entries + [extra])


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

class TestNormalisation:
    def test_casefold_and_punctuation(self):
        assert normalize_name("  O'Brien,  JAMES ") == "o brien james"

    def test_accent_transliteration(self):
        assert normalize_name("José García") == "jose garcia"

    def test_titles_stripped(self):
        assert normalize_name("Dr. John Smith") == "john smith"
        assert normalize_name("Mr John Smith") == "john smith"

    def test_dob_parts(self):
        assert parse_dob_parts("02/03/1958") == (2, 3, 1958)
        assert parse_dob_parts("dd/mm/1957") == (None, None, 1957)
        assert parse_dob_parts("garbage") == (None, None, None)


# ---------------------------------------------------------------------------
# Parser (inline fixture — no network)
# ---------------------------------------------------------------------------

class TestParser:
    def test_parse_fixture(self):
        date_generated, entries = parse_uk_sanctions_xml(FIXTURE_XML.encode("utf-8"))
        assert date_generated == date(2026, 7, 6)
        assert len(entries) == 2

        ind = next(e for e in entries if e["external_id"] == "AFG0006")
        assert ind["entity_type"] == "individual"
        # Name1..Name6 parts joined in order.
        assert ind["primary_name"] == "MOHAMMAD HASSAN AKHUND"
        assert ind["aliases"] == ["Mullah Hassan Akhund"]
        assert ind["dob"] == "dd/mm/1957"
        assert ind["raw"]["dobs"] == ["dd/mm/1957", "02/03/1958"]
        assert ind["nationalities"] == ["Afghanistan"]
        assert ind["regimes"] == ["The Afghanistan (Sanctions) (EU Exit) Regulations 2020"]
        assert ind["listed_on"] == date(2001, 1, 25)
        assert ind["raw"]["un_reference"] == "TAi.002"
        assert ind["raw"]["uk_statement_of_reasons"] == "Member of the Taliban leadership."

        ent = next(e for e in entries if e["external_id"] == "AFG0001")
        assert ent["entity_type"] == "entity"
        assert ent["primary_name"] == "HAJI KHAIRULLAH HAJI SATTAR MONEY EXCHANGE"
        assert ent["dob"] is None
        assert ent["listed_on"] == date(2012, 6, 29)

    def test_rejects_non_sanctions_xml(self):
        with pytest.raises(ValueError):
            parse_uk_sanctions_xml(b"<SomethingElse></SomethingElse>")


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

class TestMatching:
    def setup_method(self):
        self.index = make_index()

    def test_exact_match(self):
        matches = self.index.screen("Mohammad Hassan Akhund")
        assert matches
        assert matches[0].external_id == "AFG0006"
        assert matches[0].score == 100

    def test_alias_match(self):
        matches = self.index.screen("Haji Khairullah Money Exchange")
        assert matches
        top = matches[0]
        assert top.external_id == "AFG0001"
        assert top.score == 100
        assert top.matched_alias == "Haji Khairullah Money Exchange"

    def test_token_order_insensitive(self):
        matches = self.index.screen("Akhund Hassan Mohammad")
        assert matches
        assert matches[0].external_id == "AFG0006"
        assert matches[0].score == 100

    def test_accent_insensitive(self):
        matches = self.index.screen("Jose Garcia Fernandez")
        assert matches
        assert matches[0].external_id == "RUS0001"
        assert matches[0].score == 100

    def test_title_ignored(self):
        matches = self.index.screen("Mr Jose Garcia Fernandez")
        assert matches and matches[0].external_id == "RUS0001"

    def test_dob_corroboration_boosts_score(self):
        base = self.index.screen("Mohamad Hasan Akhund")  # slight misspelling
        boosted = self.index.screen("Mohamad Hasan Akhund", dob=date(1958, 3, 2))
        assert base and boosted
        assert boosted[0].score > base[0].score
        assert boosted[0].dob_note == "corroborated"

    def test_dob_year_only_corroboration(self):
        # dd/mm/1957 placeholder — year match only.
        matches = self.index.screen("Mohamad Hasan Akhund", dob=date(1957, 1, 1))
        assert matches
        assert matches[0].dob_note == "corroborated"

    def test_dob_contradiction_penalises(self):
        base = self.index.screen("Mohammad Hassan Akhund", threshold=0)
        contradicted = self.index.screen(
            "Mohammad Hassan Akhund", dob=date(1990, 1, 1), threshold=0,
        )
        base_top = next(m for m in base if m.external_id == "AFG0006")
        contra_top = next(m for m in contradicted if m.external_id == "AFG0006")
        assert contra_top.score == base_top.score - 25
        assert contra_top.dob_note == "contradicted"

    def test_dob_contradiction_can_drop_below_threshold(self):
        # A fuzzy (misspelled) name that passes on its own falls below the
        # threshold once the DOB contradicts. (An EXACT name match stays at
        # the threshold by design — never silently drop an exact-name hit.)
        base = self.index.screen("Mohamad Hasan Akhund")
        assert any(m.external_id == "AFG0006" for m in base)
        contradicted = self.index.screen("Mohamad Hasan Akhund", dob=date(1990, 1, 1))
        assert all(m.external_id != "AFG0006" for m in contradicted)

    def test_threshold_excludes_unrelated_names(self):
        assert self.index.screen("Wendy Cartwright") == []

    def test_threshold_configurable(self):
        # A partial name below the default threshold appears at a low one.
        strict = self.index.screen("Khairullah Exchange", threshold=95)
        loose = self.index.screen("Khairullah Exchange", threshold=40)
        assert len(loose) > len(strict)

    def test_entity_type_filter(self):
        matches = self.index.screen(
            "Haji Khairullah Money Exchange", entity_type="individual",
        )
        assert all(m.external_id != "AFG0001" for m in matches)

    def test_fuzzy_token_typo(self):
        matches = self.index.screen("Haji Khairulah Money Exchange")  # missing 'l'
        assert matches and matches[0].external_id == "AFG0001"


# ---------------------------------------------------------------------------
# Adjudication state transitions (pure function)
# ---------------------------------------------------------------------------

class TestDeriveCheckStatus:
    def test_no_hits_is_clear(self):
        assert derive_check_status([]) == "clear"

    def test_pending_hits_are_potential_match(self):
        assert derive_check_status(["pending"]) == "potential_match"
        assert derive_check_status(["pending", "false_positive"]) == "potential_match"

    def test_any_true_match_confirms(self):
        assert derive_check_status(["false_positive", "true_match"]) == "confirmed_match"
        assert derive_check_status(["true_match", "pending"]) == "confirmed_match"

    def test_all_false_positive_clears(self):
        assert derive_check_status(["false_positive", "false_positive"]) == "clear"

    def test_accepts_enum_members(self):
        from app.models.screening import HitAdjudicationStatus as S
        assert derive_check_status([S.TRUE_MATCH]) == "confirmed_match"
        assert derive_check_status([S.FALSE_POSITIVE]) == "clear"


# ---------------------------------------------------------------------------
# Adjudication flow on the ORM models (in-memory SQLite)
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    from app.models.screening import (
        SanctionsDataset, SanctionsEntry, ScreeningCheck, ScreeningHit,
    )

    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            SanctionsDataset.__table__,
            SanctionsEntry.__table__,
            ScreeningCheck.__table__,
            ScreeningHit.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


class TestAdjudicationFlow:
    def _make_check_with_hits(self, db, n_hits=2):
        from app.models.screening import (
            ScreeningCheck, ScreeningCheckStatus, ScreeningHit,
            ScreeningSubjectType,
        )
        check = ScreeningCheck(
            matter_id=1,
            subject_type=ScreeningSubjectType.CLIENT,
            subject_name="Test Subject",
            status=ScreeningCheckStatus.POTENTIAL_MATCH,
            dataset_version="06/07/2026",
            providers_used=["uk_fcdo_local"],
        )
        db.add(check)
        db.flush()
        for i in range(n_hits):
            db.add(ScreeningHit(
                check_id=check.id,
                source="uk_fcdo",
                category="sanctions",
                matched_name=f"Match {i}",
                external_ref=f"REF{i}",
                score=90 - i,
            ))
        db.commit()
        db.refresh(check)
        return check

    def _adjudicate(self, db, check, hit, status_value):
        from datetime import datetime, timezone
        from app.models.screening import HitAdjudicationStatus, ScreeningCheckStatus
        hit.adjudication_status = HitAdjudicationStatus(status_value)
        hit.adjudication_rationale = "A rationale of sufficient length."
        hit.adjudicated_at = datetime.now(timezone.utc)
        derived = derive_check_status(h.adjudication_status for h in check.hits)
        check.status = ScreeningCheckStatus(derived)
        check.requires_escalation = derived == "confirmed_match"
        db.commit()
        db.refresh(check)
        return check

    def test_true_match_confirms_and_escalates(self, db_session):
        check = self._make_check_with_hits(db_session)
        check = self._adjudicate(db_session, check, check.hits[0], "true_match")
        assert check.status.value == "confirmed_match"
        assert check.requires_escalation is True

    def test_partial_false_positive_stays_potential(self, db_session):
        check = self._make_check_with_hits(db_session)
        check = self._adjudicate(db_session, check, check.hits[0], "false_positive")
        assert check.status.value == "potential_match"
        assert check.requires_escalation is False

    def test_all_false_positive_clears(self, db_session):
        check = self._make_check_with_hits(db_session)
        for hit in list(check.hits):
            check = self._adjudicate(db_session, check, hit, "false_positive")
        assert check.status.value == "clear"
        assert check.requires_escalation is False

    def test_hits_cascade_delete_with_check(self, db_session):
        from app.models.screening import ScreeningHit
        check = self._make_check_with_hits(db_session)
        db_session.delete(check)
        db_session.commit()
        assert db_session.query(ScreeningHit).count() == 0


# ---------------------------------------------------------------------------
# Provider adapter (local provider + composite, no network)
# ---------------------------------------------------------------------------

class TestProviders:
    def test_dilisense_inactive_without_key(self, monkeypatch):
        monkeypatch.delenv("DILISENSE_API_KEY", raising=False)
        from app.services.screening_providers import DilisenseProvider
        provider = DilisenseProvider()
        assert provider.is_active() is False
        assert provider.screen("Anyone") == []

    def test_dilisense_category_mapping(self):
        from app.services.screening_providers import DilisenseProvider
        assert DilisenseProvider._categories_for({"source_type": "SANCTION"}) == ["sanctions"]
        assert DilisenseProvider._categories_for({"source_type": "PEP"}) == ["pep"]
        assert "adverse_media" in DilisenseProvider._categories_for({"source_type": "CRIMINAL"})
        assert DilisenseProvider._categories_for({}) == ["adverse_media"]

    def test_composite_runs_active_providers_only(self):
        from app.services.screening_providers import (
            CompositeScreener, ProviderHit, ScreeningProvider,
        )

        class FakeActive(ScreeningProvider):
            name = "fake_active"
            def screen(self, name, dob=None, entity_type=None):
                return [ProviderHit(
                    source="fake", external_ref="X1", name=name,
                    entity_type="individual", categories=["pep"], score=80,
                )]

        class FakeInactive(ScreeningProvider):
            name = "fake_inactive"
            def is_active(self):
                return False
            def screen(self, name, dob=None, entity_type=None):  # pragma: no cover
                raise AssertionError("inactive provider must not run")

        screener = CompositeScreener(db=None, providers=[FakeActive(), FakeInactive()])
        hits, used = screener.screen("Some Person")
        assert used == ["fake_active"]
        assert len(hits) == 1 and hits[0].categories == ["pep"]
