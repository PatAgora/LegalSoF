"""
Document encryption-at-rest service.

Symmetric (Fernet / AES-128-CBC + HMAC) encryption for uploaded client
documents, keyed by settings.DOCUMENT_ENCRYPTION_KEY — a urlsafe base64
32-byte Fernet key. Encrypted payloads are tagged with a versioned
magic prefix so legacy plaintext blobs (rows/files written before
encryption was enabled) pass through unchanged:

    ciphertext = b"SOFENC1:" + fernet_token

Encryption is OPTIONAL: when DOCUMENT_ENCRYPTION_KEY is unset the
encrypt/decrypt helpers are transparent no-ops on plaintext, so
existing deployments keep working. Decryption of a tagged payload
without the correct key raises a clear RuntimeError — never silently
returns ciphertext.

Also provides EncryptedLargeBinary, a SQLAlchemy TypeDecorator that
applies encrypt_bytes on bind and decrypt_bytes on load, giving
transparent at-rest encryption for LargeBinary columns.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.types import TypeDecorator, LargeBinary

from app.core.config import settings

logger = logging.getLogger(__name__)

# Versioned magic prefix identifying an encrypted payload. Bump the
# version (SOFENC2:...) if the scheme ever changes so old payloads
# remain identifiable.
ENC_PREFIX = b"SOFENC1:"

# Lazily created Fernet instance, cached against the key it was built
# from so a key change (e.g. in tests monkeypatching settings) rebuilds
# the cipher instead of reusing a stale one.
_fernet_cache: tuple[str, object] | None = None


def encryption_enabled() -> bool:
    """True only when a document encryption key is configured."""
    return bool(getattr(settings, "DOCUMENT_ENCRYPTION_KEY", "") or "")


def _get_fernet():
    """Lazily build (and cache) the Fernet instance for the configured
    key. Raises RuntimeError when no key is configured or the key is
    not a valid Fernet key."""
    global _fernet_cache
    key = (getattr(settings, "DOCUMENT_ENCRYPTION_KEY", "") or "").strip()
    if not key:
        raise RuntimeError(
            "DOCUMENT_ENCRYPTION_KEY is not set — cannot perform document "
            "encryption/decryption. Generate one with: python -c "
            "\"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    if _fernet_cache is not None and _fernet_cache[0] == key:
        return _fernet_cache[1]
    from cryptography.fernet import Fernet
    try:
        fernet = Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            "DOCUMENT_ENCRYPTION_KEY is not a valid Fernet key (must be "
            "urlsafe base64-encoded 32 bytes)."
        ) from exc
    _fernet_cache = (key, fernet)
    return fernet


def is_encrypted(data: bytes) -> bool:
    """Whether the payload carries the SOFENC1 encryption prefix."""
    return bool(data) and bytes(data).startswith(ENC_PREFIX)


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt raw document bytes for storage at rest.

    Output: b"SOFENC1:" + fernet_token. When encryption is disabled
    (no DOCUMENT_ENCRYPTION_KEY configured) the data is returned
    unchanged — plaintext storage remains supported for existing
    deployments.
    """
    if data is None:
        return data
    if not encryption_enabled():
        return data
    data = bytes(data)
    # Never double-encrypt an already-encrypted payload.
    if is_encrypted(data):
        return data
    return ENC_PREFIX + _get_fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    """Decrypt document bytes read from the database or disk.

    - Payloads starting with b"SOFENC1:" are Fernet-decrypted; a
      missing or wrong DOCUMENT_ENCRYPTION_KEY raises a clear
      RuntimeError (ciphertext is never returned to a caller).
    - Anything else is legacy plaintext and passes through unchanged.
    """
    if data is None:
        return data
    data = bytes(data)
    if not is_encrypted(data):
        return data
    token = data[len(ENC_PREFIX):]
    from cryptography.fernet import InvalidToken
    fernet = _get_fernet()  # raises RuntimeError when key missing/invalid
    try:
        return fernet.decrypt(token)
    except InvalidToken as exc:
        raise RuntimeError(
            "Failed to decrypt document: DOCUMENT_ENCRYPTION_KEY does not "
            "match the key the document was encrypted with (or the payload "
            "is corrupt)."
        ) from exc


class EncryptedLargeBinary(TypeDecorator):
    """LargeBinary column that is transparently encrypted at rest.

    encrypt_bytes on the way in (bind), decrypt_bytes on the way out
    (result). Legacy plaintext rows read back unchanged — the SOFENC1
    prefix check in decrypt_bytes handles the passthrough — so enabling
    encryption on an existing database requires no data migration.
    """
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: Optional[bytes], dialect) -> Optional[bytes]:
        if value is None:
            return None
        return encrypt_bytes(bytes(value))

    def process_result_value(self, value: Optional[bytes], dialect) -> Optional[bytes]:
        if value is None:
            return None
        return decrypt_bytes(bytes(value))
