import base64
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from app.core.signing import build_canonical_payload, format_dotnet_round_trip, format_utc_iso


def test_format_utc_iso_uses_z_suffix_and_microsecond_precision():
    dt = datetime(2026, 7, 6, 12, 35, 0, 123000, tzinfo=timezone.utc)
    assert format_utc_iso(dt) == "2026-07-06T12:35:00.123000Z"


def test_format_utc_iso_converts_non_utc_to_utc():
    dt = datetime(2026, 7, 6, 16, 35, 0, 123000, tzinfo=timezone(timedelta(hours=4)))
    assert format_utc_iso(dt) == "2026-07-06T12:35:00.123000Z"


def test_format_utc_iso_rejects_naive_datetime():
    with pytest.raises(ValueError):
        format_utc_iso(datetime(2026, 7, 6, 12, 35, 0))


def test_format_dotnet_round_trip_matches_known_dotnet_output():
    """Empirically verified against a live .NET probe: DateTimeOffset(...).ToString("O") for a
    UTC instant with 123456 microseconds is "2026-07-06T13:07:11.1234560+00:00" - 7 fractional
    digits (a trailing zero appended to Python's 6) and a numeric "+00:00" offset, never "Z"."""
    dt = datetime(2026, 7, 6, 13, 7, 11, 123456, tzinfo=timezone.utc)
    assert format_dotnet_round_trip(dt) == "2026-07-06T13:07:11.1234560+00:00"


def test_format_dotnet_round_trip_converts_non_utc_to_utc():
    dt = datetime(2026, 7, 6, 17, 7, 11, 123456, tzinfo=timezone(timedelta(hours=4)))
    assert format_dotnet_round_trip(dt) == "2026-07-06T13:07:11.1234560+00:00"


def test_canonical_payload_is_deterministic():
    expires = datetime(2026, 7, 6, 12, 35, 0, tzinfo=timezone.utc)
    a = build_canonical_payload(
        device_uuid="dev-1", request_uuid="req-1", sha256="ab" * 32,
        expires_at=expires, nonce="nonce-1",
    )
    b = build_canonical_payload(
        device_uuid="dev-1", request_uuid="req-1", sha256="ab" * 32,
        expires_at=expires, nonce="nonce-1",
    )
    assert a == b


@pytest.mark.parametrize(
    "override",
    ["device_uuid", "request_uuid", "sha256", "nonce"],
)
def test_canonical_payload_changes_when_any_field_changes(override):
    expires = datetime(2026, 7, 6, 12, 35, 0, tzinfo=timezone.utc)
    base_kwargs = dict(
        device_uuid="dev-1", request_uuid="req-1", sha256="ab" * 32,
        expires_at=expires, nonce="nonce-1",
    )
    baseline = build_canonical_payload(**base_kwargs)

    varied_kwargs = dict(base_kwargs)
    varied_kwargs[override] = varied_kwargs[override] + "-different"
    varied = build_canonical_payload(**varied_kwargs)

    assert baseline != varied


def test_canonical_payload_field_boundaries_cannot_be_shifted():
    # Without length-prefixing, "ab"+"cd" and "a"+"bcd" would concatenate identically.
    expires = datetime(2026, 7, 6, 12, 35, 0, tzinfo=timezone.utc)
    a = build_canonical_payload(
        device_uuid="ab", request_uuid="cd", sha256="ab" * 32,
        expires_at=expires, nonce="nonce-1",
    )
    b = build_canonical_payload(
        device_uuid="a", request_uuid="bcd", sha256="ab" * 32,
        expires_at=expires, nonce="nonce-1",
    )
    assert a != b


def test_sign_and_verify_round_trip():
    private_key = Ed25519PrivateKey.generate()
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    payload = build_canonical_payload(
        device_uuid="dev-1", request_uuid="req-1", sha256="ab" * 32,
        expires_at=expires, nonce="nonce-1",
    )

    signature = private_key.sign(payload)

    # Does not raise => valid.
    private_key.public_key().verify(signature, payload)


def test_tampered_payload_fails_verification():
    private_key = Ed25519PrivateKey.generate()
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    payload = build_canonical_payload(
        device_uuid="dev-1", request_uuid="req-1", sha256="ab" * 32,
        expires_at=expires, nonce="nonce-1",
    )
    signature = private_key.sign(payload)

    tampered_payload = build_canonical_payload(
        device_uuid="dev-1", request_uuid="req-1", sha256="cd" * 32,
        expires_at=expires, nonce="nonce-1",
    )

    with pytest.raises(InvalidSignature):
        private_key.public_key().verify(signature, tampered_payload)


def test_ed25519_cross_library_interop_known_vector():
    """
    This exact (public key, message, signature) triple was empirically produced and verified
    during reconciliation of this backend's contract with the real .NET agent: signed with
    Python's `cryptography` library, then verified successfully against the *actual* .NET agent's
    Ed25519Verifier (BouncyCastle-backed) in ElevateGate.Core. The message bytes below decode to
    exactly the 5 fields build_canonical_payload produces - device_uuid="device-abc",
    request_uuid="request-xyz", a sha256 hex string, expires_at in .NET "O" round-trip format
    ("2026-07-06T12:35:00.1230000+00:00"), and nonce="nonce-123" - confirming this module's byte
    layout is what the shipped agent binary actually verifies, not just what its source implies.
    """
    public_key_b64 = "tBRKExqE9S1JWa18vwBsYlnhIgjmKszgpJK1Y8k1ALY="
    signature_b64 = "wHjbfYbA63Qi8ZO/NHzJQqFKOWh3V44Jhl3jkzjJDMtoBf4WWkVCuqZIdE8VEgOuBf1R9aut2tw9lSzu5mYuDA=="
    message_hex = (
        "01000a6465766963652d616263000b726571756573742d78797a"
        "0040653362306334343239386663316331343961666266346338"
        "3939366662393234323761653431653436343962393334636134"
        "3935393931623738353262383535"
        "0021323032362d30372d30365431323a33353a30302e31323330"
        "3030302b30303a3030"
        "00096e6f6e63652d313233"
    )

    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
    signature = base64.b64decode(signature_b64)
    message = bytes.fromhex(message_hex)

    public_key.verify(signature, message)  # does not raise => interop confirmed

    # And: this backend's own builder reproduces that exact message, field-for-field.
    rebuilt = build_canonical_payload(
        device_uuid="device-abc",
        request_uuid="request-xyz",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        expires_at=datetime(2026, 7, 6, 12, 35, 0, 123000, tzinfo=timezone.utc),
        nonce="nonce-123",
    )
    assert rebuilt == message
