"""Token crypto round-trip tests. Skips if cryptography is not installed."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Skip(Exception):
    pass


def _require_crypto():
    # Catch broadly: a broken/partial cryptography install (missing _cffi_backend
    # or a panicking rust binding) raises non-ImportError errors on import/use.
    try:
        from cryptography.fernet import Fernet

        Fernet(Fernet.generate_key())  # exercise the binding
    except _Skip:
        raise
    except BaseException as e:  # noqa: BLE001
        raise _Skip(f"cryptography unusable: {type(e).__name__}")


def test_round_trip_encrypt_decrypt():
    _require_crypto()
    from portal import crypto

    os.environ["TOKEN_ENC_KEY"] = crypto.generate_key()
    secret = "ya29.super-secret-access-token"
    blob = crypto.encrypt(secret)

    assert isinstance(blob, (bytes, bytearray))
    assert secret.encode() not in blob  # ciphertext, not plaintext
    assert crypto.decrypt(blob) == secret


def test_distinct_keys_cannot_cross_decrypt():
    _require_crypto()
    from cryptography.fernet import InvalidToken

    from portal import crypto

    os.environ["TOKEN_ENC_KEY"] = crypto.generate_key()
    blob = crypto.encrypt("hello")

    os.environ["TOKEN_ENC_KEY"] = crypto.generate_key()  # rotate to a new key
    raised = False
    try:
        crypto.decrypt(blob)
    except InvalidToken:
        raised = True
    assert raised, "decrypting with the wrong key must fail"


def test_missing_key_raises_clear_error():
    _require_crypto()
    from portal import crypto

    os.environ.pop("TOKEN_ENC_KEY", None)
    raised = False
    try:
        crypto.encrypt("x")
    except RuntimeError as e:
        raised = "TOKEN_ENC_KEY" in str(e)
    assert raised, "missing key should raise a clear RuntimeError"


def _run():
    passed = skipped = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
                passed += 1
            except _Skip as e:
                print(f"  SKIP {name} ({e})")
                skipped += 1
    print(f"\n{passed} passed, {skipped} skipped.")
    return passed, skipped


if __name__ == "__main__":
    _run()
