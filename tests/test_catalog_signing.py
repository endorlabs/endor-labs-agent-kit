from __future__ import annotations

import subprocess

import pytest

from endor_agent_kit.catalog_signing import (
    der_from_raw_p1363,
    raw_p1363_from_der,
    sign_catalog,
    verify_catalog_signature,
)


def _has_openssl() -> bool:
    try:
        subprocess.run(["openssl", "version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


pytestmark = pytest.mark.skipif(not _has_openssl(), reason="openssl not available")


def _es256_keypair(tmp_path):
    private_key = tmp_path / "key.pem"
    public_key = tmp_path / "pub.pem"
    subprocess.run(
        ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(private_key)],
        check=True,
    )
    subprocess.run(
        ["openssl", "ec", "-in", str(private_key), "-pubout", "-out", str(public_key)],
        check=True,
        stderr=subprocess.DEVNULL,
    )
    return private_key, public_key


def test_sign_then_verify_round_trips(tmp_path):
    private_key, public_key = _es256_keypair(tmp_path)
    catalog = tmp_path / "catalog.json"
    catalog.write_text('{"schema_version": "v1", "agents": []}\n', encoding="utf-8")

    signature = sign_catalog(catalog, private_key)

    assert signature == tmp_path / "catalog.json.sig"
    assert signature.is_file()
    assert verify_catalog_signature(catalog, signature, public_key) == []


def test_verify_detects_tampered_catalog(tmp_path):
    private_key, public_key = _es256_keypair(tmp_path)
    catalog = tmp_path / "catalog.json"
    catalog.write_text('{"schema_version": "v1", "agents": []}\n', encoding="utf-8")
    signature = sign_catalog(catalog, private_key)

    catalog.write_text('{"schema_version": "v1", "agents": ["tampered"]}\n', encoding="utf-8")

    errors = verify_catalog_signature(catalog, signature, public_key)
    assert errors
    assert "verification failed" in errors[0]


def test_verify_rejects_wrong_key(tmp_path):
    private_key, _ = _es256_keypair(tmp_path)
    catalog = tmp_path / "catalog.json"
    catalog.write_text('{"schema_version": "v1", "agents": []}\n', encoding="utf-8")
    signature = sign_catalog(catalog, private_key)

    # An unrelated keypair must not verify the signature.
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    _, wrong_public_key = _es256_keypair(other_dir)

    assert verify_catalog_signature(catalog, signature, wrong_public_key) != []


def test_der_raw_round_trip_still_verifies(tmp_path):
    # Mirrors the AKV path: openssl produces DER; AKV produces raw r||s. Converting
    # DER -> raw -> DER must yield a signature the pinned public key still accepts.
    private_key, public_key = _es256_keypair(tmp_path)
    catalog = tmp_path / "catalog.json"
    catalog.write_text('{"schema_version": "v1", "agents": []}\n', encoding="utf-8")
    der_signature = sign_catalog(catalog, private_key)

    raw = raw_p1363_from_der(der_signature.read_bytes())
    assert len(raw) == 64  # P-256: two 32-byte integers

    rebuilt = der_from_raw_p1363(raw)
    rebuilt_path = tmp_path / "rebuilt.sig"
    rebuilt_path.write_bytes(rebuilt)

    assert verify_catalog_signature(catalog, rebuilt_path, public_key) == []


def test_der_from_raw_rejects_odd_length():
    with pytest.raises(ValueError):
        der_from_raw_p1363(b"\x01\x02\x03")


def test_der_from_raw_rejects_wrong_width():
    # Even length but not 64 bytes (not a valid ES256 r||s) must fail at the boundary.
    with pytest.raises(ValueError, match="64 bytes"):
        der_from_raw_p1363(b"\x01" * 32)


def test_verify_returns_error_when_openssl_missing(tmp_path, monkeypatch):
    import endor_agent_kit.catalog_signing as signing

    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}\n", encoding="utf-8")
    signature = tmp_path / "catalog.json.sig"
    signature.write_bytes(b"sig")
    public_key = tmp_path / "pub.pem"
    public_key.write_text("key\n", encoding="utf-8")

    def _no_openssl(*_args, **_kwargs):
        raise FileNotFoundError("openssl")

    monkeypatch.setattr(signing.subprocess, "run", _no_openssl)

    errors = signing.verify_catalog_signature(catalog, signature, public_key)
    assert errors
    assert "openssl not found" in errors[0]


def test_verify_reports_missing_signature(tmp_path):
    _, public_key = _es256_keypair(tmp_path)
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{}\n", encoding="utf-8")

    errors = verify_catalog_signature(catalog, tmp_path / "absent.sig", public_key)
    assert errors
    assert "missing" in errors[0].lower()
