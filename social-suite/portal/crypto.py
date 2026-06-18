"""Token envelope encryption helpers (Fernet / AES-128-CBC + HMAC).

OAuth tokens are encrypted before they touch the DB and decrypted only in the
poster at send time. The key comes from the ``TOKEN_ENC_KEY`` env var (a
url-safe base64 32-byte Fernet key — generate one with ``generate_key()``).

``cryptography`` is lazy-imported so that importing models / running model tests
does not require it. If it is missing when encryption is actually used, a clear
ImportError is raised.
"""

from __future__ import annotations

import os

_KEY_ENV = "TOKEN_ENC_KEY"


def _load_fernet():
    """Lazy-import cryptography and build a Fernet from ``TOKEN_ENC_KEY``."""
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover - depends on env
        raise ImportError(
            "The 'cryptography' package is required for token encryption. "
            "Install it with: pip install cryptography"
        ) from exc

    key = os.environ.get(_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"{_KEY_ENV} is not set. Generate one with "
            "portal.crypto.generate_key() and store it in your secret store."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def generate_key() -> str:
    """Return a new url-safe base64 Fernet key (store it as TOKEN_ENC_KEY)."""
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover - depends on env
        raise ImportError(
            "The 'cryptography' package is required to generate a key. "
            "Install it with: pip install cryptography"
        ) from exc
    return Fernet.generate_key().decode()


def encrypt(plaintext: str) -> bytes:
    """Encrypt a token string -> ciphertext bytes (store in *_enc columns)."""
    return _load_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(blob: bytes) -> str:
    """Decrypt ciphertext bytes -> the original token string."""
    return _load_fernet().decrypt(blob).decode("utf-8")
