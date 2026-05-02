from __future__ import annotations

from api.app.auth_tokens import compare_tokens, generate_token, hash_token


def test_generate_token_is_url_safe_and_long_enough():
    token = generate_token()
    assert len(token) >= 40
    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )
    assert set(token) <= allowed


def test_generate_token_unique_across_many_calls():
    tokens = {generate_token() for _ in range(1000)}
    assert len(tokens) == 1000


def test_hash_token_is_deterministic():
    plaintext = generate_token()
    assert hash_token(plaintext) == hash_token(plaintext)


def test_hash_token_differs_for_different_inputs():
    a = hash_token("alpha")
    b = hash_token("beta")
    assert a != b


def test_hash_token_returns_hex_sha256():
    digest = hash_token("alpha")
    assert len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")


def test_compare_tokens_matches_hash_of_plaintext():
    plaintext = generate_token()
    stored = hash_token(plaintext)
    assert compare_tokens(plaintext, stored) is True


def test_compare_tokens_rejects_wrong_plaintext():
    plaintext = generate_token()
    other = generate_token()
    stored = hash_token(plaintext)
    assert compare_tokens(other, stored) is False


def test_compare_tokens_rejects_truncated_hash():
    plaintext = generate_token()
    stored = hash_token(plaintext)[:32]
    assert compare_tokens(plaintext, stored) is False
