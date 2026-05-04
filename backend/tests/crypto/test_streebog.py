"""Streebog (GOST 34.11-2012) primitives + full hash KAT.

The implementation in `app.crypto.gost3411` keeps a hand-rolled reference
(`_S_ref`, `_P_ref`, `_L_ref`, `_LPS_ref`) verbatim from RFC 6986 alongside
an optimized T-table based `_LPS`. The module's import-time `_self_test`
already asserts the optimized path matches the reference for a handful of
inputs; these tests reinforce that with a wider corpus, plus they freeze
known answers so any future refactor that breaks the hash will fail loudly.
"""
from __future__ import annotations

import os

import pytest

from app.crypto.gost3411 import streebog_256, streebog_512
from app.crypto.gost3411.constants import A, PI, TAU
from app.crypto.gost3411.streebog import (
    _LPS,
    _L_ref,
    _LPS_ref,
    _P_ref,
    _S_ref,
    _hash_with_ref_LPS,
)


# ── PI / TAU constants vs RFC 6986 ───────────────────────────────────────


def test_pi_constant_matches_rfc_6986() -> None:
    """RFC 6986 §A: PI is a fixed 256-byte non-linear substitution."""
    assert len(PI) == 256
    # First and last entries pinned from the RFC.
    assert PI[0] == 252
    assert PI[1] == 238
    assert PI[255] == 182
    # PI is a permutation — every byte value appears exactly once.
    assert sorted(PI) == list(range(256))


def test_tau_constant_matches_rfc_6986() -> None:
    """TAU rearranges 64 bytes as the transpose of an 8x8 byte matrix."""
    assert len(TAU) == 64
    assert TAU[:8] == (0, 8, 16, 24, 32, 40, 48, 56)
    assert TAU[8:16] == (1, 9, 17, 25, 33, 41, 49, 57)
    # TAU is a permutation of 0..63.
    assert sorted(TAU) == list(range(64))


def test_a_matrix_size() -> None:
    assert len(A) == 64
    # A[0] is the spec's first matrix row, written little-endian-agnostic.
    assert A[0] == 0x8E20FAA72BA0B470


# ── S / P primitives ─────────────────────────────────────────────────────


def test_S_is_byte_wise_PI_application() -> None:
    """S substitutes each byte through the PI table, independently."""
    msg = bytes(range(64))
    s = _S_ref(msg)
    assert s == bytes(PI[b] for b in msg)


def test_P_is_pure_permutation() -> None:
    """P preserves the multiset of bytes — only permutes positions."""
    msg = os.urandom(64)
    p = _P_ref(msg)
    assert sorted(p) == sorted(msg)
    assert p == bytes(msg[TAU[i]] for i in range(64))


def test_L_is_linear_over_xor() -> None:
    """L is a linear map: L(a XOR b) == L(a) XOR L(b) for any 64-byte a, b."""
    a = os.urandom(64)
    b = os.urandom(64)
    ab = bytes(x ^ y for x, y in zip(a, b))
    la = _L_ref(a)
    lb = _L_ref(b)
    lab = _L_ref(ab)
    assert lab == bytes(x ^ y for x, y in zip(la, lb))


# ── optimized vs reference LPS over a wide random corpus ─────────────────


def test_lps_optimized_matches_reference_random() -> None:
    """Wider version of the module's import-time self-test."""
    cases = [b"\x00" * 64, b"\xff" * 64, bytes(range(64))]
    cases.extend(os.urandom(64) for _ in range(64))
    for x in cases:
        assert _LPS(x) == _LPS_ref(x), f"diverges at {x.hex()}"


# ── full hash: optimized vs spec-true reference path ─────────────────────


@pytest.mark.parametrize(
    "msg",
    [
        b"",
        b"a",
        b"hello world",
        b"x" * 63,
        b"x" * 64,
        b"x" * 65,
        b"x" * 127,
        b"x" * 128,
        bytes(range(200)),
    ],
)
def test_streebog_256_matches_reference_path(msg: bytes) -> None:
    assert streebog_256(msg) == _hash_with_ref_LPS(msg, 256)


@pytest.mark.parametrize(
    "msg",
    [
        b"",
        b"a",
        b"hello world",
        b"x" * 64,
        b"x" * 200,
    ],
)
def test_streebog_512_matches_reference_path(msg: bytes) -> None:
    assert streebog_512(msg) == _hash_with_ref_LPS(msg, 512)


def test_streebog_random_inputs_optimized_vs_reference() -> None:
    for _ in range(8):
        msg = os.urandom(300)
        assert streebog_256(msg) == _hash_with_ref_LPS(msg, 256)
        assert streebog_512(msg) == _hash_with_ref_LPS(msg, 512)


# ── known-answer tests: digests frozen as regression guard ───────────────
#
# Generated once from the implementation (which is internally consistent —
# its own self-test pins optimized LPS to the reference LPS). If anyone
# changes the algorithm or the constants, these will fail and force an
# explicit decision.


KAT_256 = {
    b"": "bbe19c8d2025d99f943a932a0b365a822aa36a4c479d22cc02c8973e219a533f",
    b"a": "dc6c719fb649286ad64f877fd798d95e51419c231e13b2a0d38a9a1a9bd7c9e9",
    b"hello world": "db71c1b20c84b5fae9b14fa58fce48acd28df424a13cd7edab61c986b0887367",
}

KAT_512 = {
    b"": (
        "8a1a1c4cbf909f8ecb81cd1b5c713abad26a4cac2a5fda3ce86e352855712f36"
        "a7f0be98eb6cf51553b507b73a87e97946aebc29859255049f86aa09a25d948e"
    ),
}


@pytest.mark.parametrize("msg,expected_hex", list(KAT_256.items()))
def test_streebog_256_kat(msg: bytes, expected_hex: str) -> None:
    assert streebog_256(msg).hex() == expected_hex


@pytest.mark.parametrize("msg,expected_hex", list(KAT_512.items()))
def test_streebog_512_kat(msg: bytes, expected_hex: str) -> None:
    assert streebog_512(msg).hex() == expected_hex


# ── basic properties ─────────────────────────────────────────────────────


def test_digest_sizes() -> None:
    assert len(streebog_256(b"abc")) == 32
    assert len(streebog_512(b"abc")) == 64


def test_streebog_is_deterministic() -> None:
    msg = b"deterministic test " * 20
    assert streebog_256(msg) == streebog_256(msg)
    assert streebog_512(msg) == streebog_512(msg)


def test_avalanche_one_bit_flip() -> None:
    """A 1-bit change must produce a wildly different digest (>50 bits flip on average)."""
    msg = b"avalanche test message" + b"\x00" * 50
    flipped = bytes([msg[0] ^ 0x01]) + msg[1:]
    a = streebog_256(msg)
    b = streebog_256(flipped)
    diff_bits = sum(bin(x ^ y).count("1") for x, y in zip(a, b))
    assert diff_bits > 64, f"only {diff_bits} bit differences — avalanche broken"
