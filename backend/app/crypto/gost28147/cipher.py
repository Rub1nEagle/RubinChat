"""GOST 28147-89 block cipher (64-bit block, 256-bit key) — optimized manual.

Feistel network with 32 rounds. Round subkeys K_0..K_7 are derived by
splitting the 256-bit key into eight 32-bit big-endian words. Round
schedule: K_0..K_7 three times (rounds 1-24), then K_7..K_0 (rounds
25-32).

Performance notes
-----------------
The round function is ``f(x, k) = rol11(t((x + k) mod 2^32))`` where ``t``
applies eight nibble S-boxes. Naive ``t`` does eight nibble extracts and
shifts per call, plus a separate 32-bit rotation. We precompute four
256-entry tables ``T0..T3`` such that

    t(x) = T0[x & 0xFF] ^ T1[(x >> 8) & 0xFF] ^ T2[(x >> 16) & 0xFF] ^ T3[(x >> 24) & 0xFF]

with each ``Tk[b]`` already pre-shifted to its byte position and pre-rotated
by 11 bits, so the rotation in ``f`` is folded in too. That replaces ~16
shifts and 8 nibble lookups per call with 4 byte-indexed lookups + 3 XORs.

The reference function ``_t_ref`` (kept verbatim from the spec) is only used
by the startup self-test that asserts the optimized impl matches it on a
handful of inputs.
"""
from __future__ import annotations

from .sboxes import SBOX

_MASK32 = 0xFFFFFFFF


# ─────────────────────────── reference (spec-true) ─────────────────────────────

def _t_ref(x: int) -> int:
    out = 0
    for i in range(8):
        nibble = (x >> (4 * i)) & 0xF
        out |= SBOX[i][nibble] << (4 * i)
    return out


def _f_ref(x: int, k: int) -> int:
    s = _t_ref((x + k) & _MASK32)
    return ((s << 11) | (s >> 21)) & _MASK32


# ─────────────────── precomputed tables (S-box + rol-11) ───────────────────────
#
# T0[b] covers byte 0 (bits 0..7) of the input word.
# T1[b] covers byte 1 (bits 8..15).
# T2[b] covers byte 2 (bits 16..23).
# T3[b] covers byte 3 (bits 24..31).
#
# Each entry is the pre-rotated contribution to a 32-bit output. Composition
# (XOR / OR) of contributions from non-overlapping bit ranges is preserved
# under rol11, so we can pre-rotate each table independently.

def _build_t_tables() -> tuple[tuple[int, ...], ...]:
    base = [[0] * 256 for _ in range(4)]
    for b in range(256):
        lo, hi = b & 0xF, (b >> 4) & 0xF
        # byte 0: SBOX[0] lo nibble, SBOX[1] hi nibble → at bit 0
        base[0][b] = (SBOX[1][hi] << 4) | SBOX[0][lo]
        # byte 1: SBOX[2] / SBOX[3] → at bit 8
        base[1][b] = ((SBOX[3][hi] << 4) | SBOX[2][lo]) << 8
        # byte 2: SBOX[4] / SBOX[5] → at bit 16
        base[2][b] = ((SBOX[5][hi] << 4) | SBOX[4][lo]) << 16
        # byte 3: SBOX[6] / SBOX[7] → at bit 24
        base[3][b] = ((SBOX[7][hi] << 4) | SBOX[6][lo]) << 24
    rotated = []
    for tbl in base:
        rotated.append(tuple(((v << 11) | (v >> 21)) & _MASK32 for v in tbl))
    return tuple(rotated)


_T0, _T1, _T2, _T3 = _build_t_tables()


def _f(x: int, k: int) -> int:
    """Round function fused with rol-11."""
    s = (x + k) & _MASK32
    return _T0[s & 0xFF] ^ _T1[(s >> 8) & 0xFF] ^ _T2[(s >> 16) & 0xFF] ^ _T3[(s >> 24) & 0xFF]


# ───────────────────────────── key schedule ────────────────────────────────────

def expand_key(key: bytes) -> tuple[int, ...]:
    """Public: split 256-bit key into 8 × 32-bit subkeys."""
    if len(key) != 32:
        raise ValueError("GOST 28147 key must be 32 bytes (256 bits)")
    return tuple(int.from_bytes(key[i * 4:(i + 1) * 4], "big") for i in range(8))


# Precomputed round-index sequences (same instance reused, no per-call rebuild).
_ROUND_ENC: tuple[int, ...] = tuple(range(8)) * 3 + tuple(range(7, -1, -1))
_ROUND_DEC: tuple[int, ...] = tuple(range(8)) + tuple(range(7, -1, -1)) * 3


# ───────────────────────────── block primitives ────────────────────────────────

def encrypt_block_with_subkeys(block: bytes, subkeys: tuple[int, ...]) -> bytes:
    """Hot-path variant: caller supplies pre-expanded subkeys."""
    if len(block) != 8:
        raise ValueError("block must be 8 bytes")
    n1 = int.from_bytes(block[:4], "big")
    n2 = int.from_bytes(block[4:], "big")
    for idx in _ROUND_ENC:
        n1, n2 = (n2 ^ _f(n1, subkeys[idx])) & _MASK32, n1
    return n2.to_bytes(4, "big") + n1.to_bytes(4, "big")


def decrypt_block_with_subkeys(block: bytes, subkeys: tuple[int, ...]) -> bytes:
    if len(block) != 8:
        raise ValueError("block must be 8 bytes")
    n1 = int.from_bytes(block[:4], "big")
    n2 = int.from_bytes(block[4:], "big")
    for idx in _ROUND_DEC:
        n1, n2 = (n2 ^ _f(n1, subkeys[idx])) & _MASK32, n1
    return n2.to_bytes(4, "big") + n1.to_bytes(4, "big")


def encrypt_block(block: bytes, key: bytes) -> bytes:
    return encrypt_block_with_subkeys(block, expand_key(key))


def decrypt_block(block: bytes, key: bytes) -> bytes:
    return decrypt_block_with_subkeys(block, expand_key(key))


# ─────────────────────────────── self-test ─────────────────────────────────

def _self_test() -> None:
    import os

    # 1. _t / _f equivalence on random 32-bit values.
    for _ in range(64):
        x = int.from_bytes(os.urandom(4), "big")
        k = int.from_bytes(os.urandom(4), "big")
        if _f(x, k) != _f_ref(x, k):
            raise RuntimeError(
                "GOST 28147 optimized round function diverges from reference — "
                "refusing to load."
            )

    # 2. encrypt/decrypt roundtrip.
    for _ in range(8):
        key = os.urandom(32)
        blk = os.urandom(8)
        ct = encrypt_block(blk, key)
        if decrypt_block(ct, key) != blk:
            raise RuntimeError(
                "GOST 28147 encrypt/decrypt roundtrip failed — refusing to load."
            )


_self_test()


# ─────────────────────── backwards-compatible aliases ──────────────────────────
# These existed before the optimization and may be imported from elsewhere.
_t = _t_ref
_expand_key = expand_key
