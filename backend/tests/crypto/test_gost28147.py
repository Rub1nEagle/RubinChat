"""GOST 28147-89 (Magma S-boxes / CryptoPro-A paramset) ECB + CTR tests.

The implementation in `app.crypto.gost28147` keeps a hand-rolled reference
round function `_f_ref` alongside an optimized 4-table `_f`. We exercise:

* round-function equivalence over a wide random corpus,
* ECB block encrypt/decrypt round-trip,
* CTR encrypt/decrypt round-trip (CTR is symmetric — same call decrypts),
* keystream determinism: same (key, nonce) ⇒ same ciphertext,
* keystream sensitivity: changing the key OR the nonce produces different
  ciphertext for the same plaintext,
* known-answer regression vectors so any future refactor that breaks the
  cipher is caught loudly.
"""
from __future__ import annotations

import os

import pytest

from app.crypto.gost28147 import ctr_crypt, decrypt_block, encrypt_block
from app.crypto.gost28147.cipher import _f, _f_ref


# ── round function: optimized vs spec-true reference ────────────────────


def test_round_function_optimized_matches_reference_random() -> None:
    """`_f` is a fused 4-table implementation; `_f_ref` is the spec form."""
    for _ in range(256):
        x = int.from_bytes(os.urandom(4), "big")
        k = int.from_bytes(os.urandom(4), "big")
        assert _f(x, k) == _f_ref(x, k)


# ── ECB block primitives ────────────────────────────────────────────────


def test_ecb_encrypt_decrypt_roundtrip_random() -> None:
    for _ in range(32):
        key = os.urandom(32)
        pt = os.urandom(8)
        ct = encrypt_block(pt, key)
        assert decrypt_block(ct, key) == pt


def test_ecb_block_size_invariants() -> None:
    """Block must be exactly 8 bytes; key must be exactly 32 bytes."""
    with pytest.raises(ValueError):
        encrypt_block(b"\x00" * 7, b"\x00" * 32)
    with pytest.raises(ValueError):
        encrypt_block(b"\x00" * 9, b"\x00" * 32)
    with pytest.raises(ValueError):
        encrypt_block(b"\x00" * 8, b"\x00" * 31)


def test_ecb_kat_known_vectors() -> None:
    """Frozen vectors generated from the implementation. Regression guard
    for accidental changes to S-boxes, key schedule, or round permutation.
    """
    # Block of zeros, key of zeros.
    assert encrypt_block(b"\x00" * 8, b"\x00" * 32).hex() == "fe674e976b7dc1d9"
    # Block 0..7, key 0..31.
    assert encrypt_block(bytes(range(8)), bytes(range(32))).hex() == "1f5259f5a556f2aa"


def test_ecb_different_keys_yield_different_ciphertext() -> None:
    pt = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    k1 = b"\x00" * 32
    k2 = b"\xff" * 32
    assert encrypt_block(pt, k1) != encrypt_block(pt, k2)


# ── CTR mode ─────────────────────────────────────────────────────────────


def test_ctr_roundtrip_aligned() -> None:
    key = os.urandom(32)
    nonce = os.urandom(8)
    pt = b"The quick brown fox jumps over the lazy dog!!!!"  # 47 bytes — non-aligned tail
    ct = ctr_crypt(pt, key, nonce)
    assert ct != pt
    assert ctr_crypt(ct, key, nonce) == pt


@pytest.mark.parametrize("size", [0, 1, 7, 8, 9, 63, 64, 65, 256, 1024, 16_384])
def test_ctr_roundtrip_various_sizes(size: int) -> None:
    key = os.urandom(32)
    nonce = os.urandom(8)
    pt = os.urandom(size)
    ct = ctr_crypt(pt, key, nonce)
    assert len(ct) == size
    assert ctr_crypt(ct, key, nonce) == pt


def test_ctr_keystream_is_deterministic() -> None:
    key = b"\xab" * 32
    nonce = b"\xcd" * 8
    pt = b"hello GOST CTR mode"
    assert ctr_crypt(pt, key, nonce) == ctr_crypt(pt, key, nonce)


def test_ctr_changing_nonce_changes_ciphertext() -> None:
    key = b"\xab" * 32
    pt = b"hello GOST CTR mode"
    ct1 = ctr_crypt(pt, key, b"\x00" * 8)
    ct2 = ctr_crypt(pt, key, b"\x00" * 7 + b"\x01")
    assert ct1 != ct2


def test_ctr_changing_key_changes_ciphertext() -> None:
    nonce = b"\xcd" * 8
    pt = b"hello GOST CTR mode"
    ct1 = ctr_crypt(pt, b"\x00" * 32, nonce)
    ct2 = ctr_crypt(pt, b"\xff" * 32, nonce)
    assert ct1 != ct2


def test_ctr_rejects_wrong_nonce_size() -> None:
    with pytest.raises(ValueError):
        ctr_crypt(b"hi", b"\x00" * 32, b"\x00" * 7)


def test_ctr_kat_known_vector() -> None:
    """Regression guard for the CTR composition (block primitive + counter)."""
    pt = b"The quick brown fox jumps over the lazy dog"
    key = bytes(range(32))
    nonce = bytes(8)
    expected = (
        "e0c4ee76693336f399602a47280067152a8279b1f40e2f21d8d87a43369460708b"
        "54873ca02a7c54080c89"
    )
    assert ctr_crypt(pt, key, nonce).hex() == expected


def test_ctr_empty_input_returns_empty() -> None:
    """No keystream is consumed when there is nothing to encrypt."""
    assert ctr_crypt(b"", b"\x00" * 32, b"\x00" * 8) == b""
