"""Detached ECDSA-P256 signing/verification for ``catalog.json``.

The signed ``catalog.json`` is the load-bearing release artifact apiserver
verifies. Production signing is HSM-backed via Azure Key Vault
(ECDSA-P256 / ES256) over an OIDC-federated GitHub Actions job -- no signing key
is stored in GitHub (see ``RELEASES.md``). This module owns the
*offline* verification side, which apiserver mirrors: a detached signature over
the raw ``catalog.json`` bytes, verified against a pinned public key.

Crypto is delegated to ``openssl`` (a system tool, like ``git``) so the package
stays dependency-free. Signatures are ASN.1 DER over the SHA-256 digest, the
shape ``openssl dgst -verify`` and Go's ``ecdsa.VerifyASN1`` both accept.
"""

from __future__ import annotations

import base64
from pathlib import Path
import subprocess

SIGNATURE_SUFFIX = ".sig"
_ES256_RAW_LEN = 64  # P-256 r||s: two 32-byte integers
_ES256_DIGEST_LEN = 32  # SHA-256 digest fed to ES256 sign


def akv_digest_arg(digest: bytes) -> str:
    """Encode a SHA-256 digest for ``az keyvault key sign --digest``.

    The CLI decodes ``--digest`` with standard ``base64.b64decode``, which
    silently discards base64url's ``-``/``_`` characters. A base64url digest that
    happens to contain them therefore reaches Key Vault short of 32 bytes and is
    rejected ("ES256 requires 32 bytes"); standard padded base64 survives that
    decoder intact.
    """

    if len(digest) != _ES256_DIGEST_LEN:
        raise ValueError(f"ES256 digest must be {_ES256_DIGEST_LEN} bytes (SHA-256); got {len(digest)}")
    return base64.b64encode(digest).decode("ascii")


def der_from_raw_p1363(raw: bytes) -> bytes:
    """Convert a raw P1363 ES256 signature (r||s) to ASN.1 DER.

    Azure Key Vault's ES256 sign returns the fixed-width ``r||s`` form, but the
    pinned-public-key verifiers (``openssl dgst -verify``, Go ``ecdsa.VerifyASN1``)
    expect DER. This is ES256/P-256 only, so ``raw`` must be exactly 64 bytes; a
    wrong width (e.g. a misconfigured key or truncated AKV response) fails loudly
    here rather than producing a bad signature that only fails at verify time.
    """

    if len(raw) != _ES256_RAW_LEN:
        raise ValueError(f"ES256 raw signature must be {_ES256_RAW_LEN} bytes (r||s over P-256); got {len(raw)}")
    half = len(raw) // 2
    r = int.from_bytes(raw[:half], "big")
    s = int.from_bytes(raw[half:], "big")
    body = _der_uint(r) + _der_uint(s)
    if len(body) >= 0x80:
        raise ValueError("DER body too long for single-byte length encoding")
    return b"\x30" + bytes([len(body)]) + body


def raw_p1363_from_der(der: bytes, *, size: int = 32) -> bytes:
    """Convert an ASN.1 DER ECDSA signature back to raw ``r||s`` (test helper)."""

    if der[0] != 0x30:
        raise ValueError("not a DER SEQUENCE")
    # P-256 signatures always use short-form (single-byte) lengths; reject long-form
    # rather than mis-parsing at a hardcoded offset.
    if der[1] & 0x80:
        raise ValueError("long-form DER SEQUENCE length not supported (expected P-256 short form)")
    index = 2
    integers: list[int] = []
    for _ in range(2):
        if der[index] != 0x02:
            raise ValueError("expected DER INTEGER")
        length = der[index + 1]
        if length & 0x80:
            raise ValueError("long-form DER INTEGER length not supported (expected P-256 short form)")
        start = index + 2
        integers.append(int.from_bytes(der[start : start + length], "big"))
        index = start + length
    r, s = integers
    return r.to_bytes(size, "big") + s.to_bytes(size, "big")


def _der_uint(value: int) -> bytes:
    encoded = value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")
    if encoded[0] & 0x80:  # prepend 0x00 so the integer stays positive
        encoded = b"\x00" + encoded
    return b"\x02" + bytes([len(encoded)]) + encoded


def sign_catalog(
    catalog_path: str | Path,
    private_key_path: str | Path,
    signature_path: str | Path | None = None,
) -> Path:
    """Write a detached ECDSA-P256 signature for ``catalog_path`` and return its path.

    Used by tests and as the local/non-AKV signing path. The production release
    signs via Azure Key Vault; both produce a DER ECDSA-SHA256 signature.
    """

    catalog = Path(catalog_path)
    signature = Path(signature_path) if signature_path is not None else catalog.with_name(catalog.name + SIGNATURE_SUFFIX)
    subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-sign",
            str(private_key_path),
            "-out",
            str(signature),
            str(catalog),
        ],
        check=True,
    )
    return signature


def verify_catalog_signature(
    catalog_path: str | Path,
    signature_path: str | Path,
    public_key_path: str | Path,
) -> list[str]:
    """Return errors verifying the detached signature; empty list means verified."""

    catalog = Path(catalog_path)
    signature = Path(signature_path)
    public_key = Path(public_key_path)

    if not catalog.is_file():
        return [f"catalog signature verification failed: {catalog} is missing"]
    if not signature.is_file():
        return [f"catalog signature verification failed: signature {signature} is missing"]
    if not public_key.is_file():
        return [f"catalog signature verification failed: public key {public_key} is missing"]

    try:
        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(public_key),
                "-signature",
                str(signature),
                str(catalog),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        return ["catalog signature verification failed: openssl not found on PATH"]
    if result.returncode == 0 and "Verified OK" in result.stdout:
        return []
    detail = (result.stdout + result.stderr).strip().splitlines()
    reason = detail[-1] if detail else "signature mismatch"
    return [f"catalog signature verification failed: {reason}"]
