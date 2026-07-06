"""
Unit tests for the document encryption-at-rest service
(app/services/crypto.py).

Covers: encrypt/decrypt round-trip, legacy plaintext passthrough,
is_encrypted, disabled-mode passthrough, wrong-key / missing-key
errors, and the EncryptedLargeBinary TypeDecorator via in-memory
SQLite.

Run with: pytest tests/test_crypto.py -v
"""
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cryptography.fernet import Fernet

from app.core.config import settings
from app.services import crypto
from app.services.crypto import (
    ENC_PREFIX,
    EncryptedLargeBinary,
    decrypt_bytes,
    encrypt_bytes,
    encryption_enabled,
    is_encrypted,
)

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()

SAMPLE = b"%PDF-1.7 fake bank statement bytes \x00\x01\x02" * 50


@pytest.fixture
def with_key(monkeypatch):
    """Encryption enabled with KEY_A."""
    monkeypatch.setattr(settings, "DOCUMENT_ENCRYPTION_KEY", KEY_A)
    yield KEY_A


@pytest.fixture
def without_key(monkeypatch):
    """Encryption disabled (no key configured)."""
    monkeypatch.setattr(settings, "DOCUMENT_ENCRYPTION_KEY", "")
    yield


# ---------------------------------------------------------------------------
# encryption_enabled
# ---------------------------------------------------------------------------

def test_encryption_enabled_true_with_key(with_key):
    assert encryption_enabled() is True


def test_encryption_enabled_false_without_key(without_key):
    assert encryption_enabled() is False


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_round_trip(with_key):
    token = encrypt_bytes(SAMPLE)
    assert token != SAMPLE
    assert token.startswith(ENC_PREFIX)
    assert decrypt_bytes(token) == SAMPLE


def test_encrypt_output_format(with_key):
    token = encrypt_bytes(b"hello")
    assert token.startswith(b"SOFENC1:")
    # The remainder must be a valid Fernet token for the configured key.
    assert Fernet(KEY_A.encode()).decrypt(token[len(ENC_PREFIX):]) == b"hello"


def test_encrypt_does_not_double_encrypt(with_key):
    once = encrypt_bytes(SAMPLE)
    twice = encrypt_bytes(once)
    assert twice == once
    assert decrypt_bytes(twice) == SAMPLE


def test_round_trip_empty_bytes(with_key):
    token = encrypt_bytes(b"")
    assert is_encrypted(token)
    assert decrypt_bytes(token) == b""


# ---------------------------------------------------------------------------
# Legacy plaintext passthrough
# ---------------------------------------------------------------------------

def test_decrypt_plaintext_passthrough_with_key(with_key):
    """Legacy plaintext rows/files read back unchanged even when a key
    is configured."""
    assert decrypt_bytes(SAMPLE) == SAMPLE


def test_decrypt_plaintext_passthrough_without_key(without_key):
    assert decrypt_bytes(SAMPLE) == SAMPLE


# ---------------------------------------------------------------------------
# is_encrypted
# ---------------------------------------------------------------------------

def test_is_encrypted(with_key):
    assert is_encrypted(encrypt_bytes(SAMPLE)) is True
    assert is_encrypted(SAMPLE) is False
    assert is_encrypted(b"") is False
    assert is_encrypted(b"SOFENC1:whatever") is True


# ---------------------------------------------------------------------------
# Disabled mode
# ---------------------------------------------------------------------------

def test_encrypt_disabled_returns_data_unchanged(without_key):
    assert encrypt_bytes(SAMPLE) == SAMPLE
    assert is_encrypted(encrypt_bytes(SAMPLE)) is False


# ---------------------------------------------------------------------------
# Wrong / missing key errors
# ---------------------------------------------------------------------------

def test_decrypt_with_wrong_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_ENCRYPTION_KEY", KEY_A)
    token = encrypt_bytes(SAMPLE)
    monkeypatch.setattr(settings, "DOCUMENT_ENCRYPTION_KEY", KEY_B)
    with pytest.raises(RuntimeError, match="does not match"):
        decrypt_bytes(token)


def test_decrypt_encrypted_payload_without_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_ENCRYPTION_KEY", KEY_A)
    token = encrypt_bytes(SAMPLE)
    monkeypatch.setattr(settings, "DOCUMENT_ENCRYPTION_KEY", "")
    with pytest.raises(RuntimeError, match="DOCUMENT_ENCRYPTION_KEY is not set"):
        decrypt_bytes(token)


def test_invalid_key_raises_clear_error(monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_ENCRYPTION_KEY", "not-a-fernet-key")
    with pytest.raises(RuntimeError, match="not a valid Fernet key"):
        encrypt_bytes(SAMPLE)


# ---------------------------------------------------------------------------
# EncryptedLargeBinary TypeDecorator round-trip (in-memory SQLite)
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_session():
    from sqlalchemy import create_engine, Column, Integer
    from sqlalchemy.orm import declarative_base, sessionmaker

    Base = declarative_base()

    class Blob(Base):
        __tablename__ = "blobs"
        id = Column(Integer, primary_key=True)
        payload = Column(EncryptedLargeBinary, nullable=True)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, Blob, engine
    session.close()
    engine.dispose()


def test_type_decorator_round_trip_encrypted(with_key, sqlite_session):
    from sqlalchemy import text
    session, Blob, engine = sqlite_session

    session.add(Blob(id=1, payload=SAMPLE))
    session.commit()
    session.expunge_all()

    # Raw column value on disk is encrypted (SOFENC1 prefix)...
    raw = session.execute(text("SELECT payload FROM blobs WHERE id = 1")).scalar()
    assert bytes(raw).startswith(ENC_PREFIX)
    assert bytes(raw) != SAMPLE

    # ...but reads back decrypted through the ORM.
    row = session.query(Blob).filter(Blob.id == 1).one()
    assert row.payload == SAMPLE


def test_type_decorator_plaintext_legacy_row(with_key, sqlite_session):
    """A pre-encryption plaintext row (written directly, bypassing the
    ORM bind) reads back unchanged — the SOFENC1 check handles it."""
    from sqlalchemy import text
    session, Blob, engine = sqlite_session

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO blobs (id, payload) VALUES (2, :p)"),
            {"p": SAMPLE},
        )

    row = session.query(Blob).filter(Blob.id == 2).one()
    assert row.payload == SAMPLE


def test_type_decorator_disabled_mode_stores_plaintext(without_key, sqlite_session):
    from sqlalchemy import text
    session, Blob, engine = sqlite_session

    session.add(Blob(id=3, payload=SAMPLE))
    session.commit()
    session.expunge_all()

    raw = session.execute(text("SELECT payload FROM blobs WHERE id = 3")).scalar()
    assert bytes(raw) == SAMPLE

    row = session.query(Blob).filter(Blob.id == 3).one()
    assert row.payload == SAMPLE


def test_type_decorator_none_round_trip(with_key, sqlite_session):
    session, Blob, engine = sqlite_session
    session.add(Blob(id=4, payload=None))
    session.commit()
    session.expunge_all()
    row = session.query(Blob).filter(Blob.id == 4).one()
    assert row.payload is None
