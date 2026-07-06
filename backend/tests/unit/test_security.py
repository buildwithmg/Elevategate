import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    generate_device_secret,
    hash_secret,
    verify_secret,
)


def test_hash_secret_does_not_return_plaintext():
    hashed = hash_secret("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert hashed.startswith("$argon2")


def test_verify_secret_accepts_correct_plaintext():
    hashed = hash_secret("my-password")
    assert verify_secret("my-password", hashed) is True


def test_verify_secret_rejects_wrong_plaintext():
    hashed = hash_secret("my-password")
    assert verify_secret("not-my-password", hashed) is False


def test_verify_secret_rejects_malformed_hash_without_raising():
    assert verify_secret("anything", "not-a-real-hash") is False


def test_generate_device_secret_is_random_and_reasonably_long():
    a = generate_device_secret()
    b = generate_device_secret()
    assert a != b
    assert len(a) >= 32


def test_jwt_round_trip():
    token = create_access_token(subject="42", role="admin")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"


def test_jwt_tampered_signature_is_rejected():
    token = create_access_token(subject="42", role="admin")
    # Flip a character a few positions before the end, not the very last one: base64's final
    # character can have "don't-care" padding bits, so some flips there decode to the exact same
    # bytes and wouldn't actually tamper with anything - flaky in a way that depends on the
    # specific token's last character.
    target_index = -6
    flipped_char = "x" if token[target_index] != "x" else "y"
    tampered = token[:target_index] + flipped_char + token[target_index + 1 :]
    with pytest.raises(TokenError):
        decode_access_token(tampered)


def test_jwt_wrong_secret_is_rejected(monkeypatch):
    token = create_access_token(subject="42", role="admin")

    from app import config as config_module

    config_module.get_settings.cache_clear()
    monkeypatch.setenv("JWT_SECRET_KEY", "a-completely-different-secret-key")
    config_module.get_settings.cache_clear()
    try:
        with pytest.raises(TokenError):
            decode_access_token(token)
    finally:
        config_module.get_settings.cache_clear()
