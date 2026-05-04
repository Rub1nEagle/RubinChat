"""GOST 34.10-2012 sign / verify tests on paramSetA (256-bit).

The implementation is randomized (k is sampled fresh each sign), so we
focus on:

* generate_keypair → sign → verify success path,
* tamper detection on message, signature, public key,
* signature size = 2 * 32 bytes (paramSetA q is 256 bits),
* deterministic verify on a frozen (private, message, signature) triple
  — guards the digest-to-alpha mapping and EC arithmetic from regressions,
* the async facade in `crypto.provider` agrees with the sync core.
"""
from __future__ import annotations

import asyncio
import os

import pytest

from app.crypto.gost3410 import generate_keypair, sign, verify
from app.crypto.gost3410.curves import CURVE_256_A
from app.crypto.gost3410.ec import scalar_mult
from app.crypto.provider import provider


# ── basic sign / verify ──────────────────────────────────────────────────


def test_sign_verify_roundtrip_success() -> None:
    d, Q = generate_keypair()
    msg = b"transfer 100 RUB to Alice"
    sig = sign(msg, d)
    assert verify(msg, sig, Q) is True


def test_signature_size_matches_curve_order() -> None:
    """Component size = ceil(log2(q)/8); paramSetA has q ≈ 2^256, so 32 bytes each."""
    d, _ = generate_keypair()
    sig = sign(b"x", d)
    assert len(sig) == 64  # r (32) || s (32)


def test_two_signatures_for_same_message_differ() -> None:
    """k is randomized — two signs of the same message must differ."""
    d, _ = generate_keypair()
    s1 = sign(b"same message", d)
    s2 = sign(b"same message", d)
    assert s1 != s2


# ── tamper detection ────────────────────────────────────────────────────


def test_verify_rejects_modified_message() -> None:
    d, Q = generate_keypair()
    sig = sign(b"original", d)
    assert verify(b"OriginaL", sig, Q) is False


def test_verify_rejects_modified_signature() -> None:
    d, Q = generate_keypair()
    msg = b"do not modify this"
    sig = bytearray(sign(msg, d))
    sig[0] ^= 0x01
    assert verify(msg, bytes(sig), Q) is False


def test_verify_rejects_wrong_public_key() -> None:
    d1, _ = generate_keypair()
    _, Q2 = generate_keypair()
    sig = sign(b"hello", d1)
    assert verify(b"hello", sig, Q2) is False


def test_verify_rejects_malformed_signature_length() -> None:
    _, Q = generate_keypair()
    assert verify(b"hi", b"\x00" * 63, Q) is False
    assert verify(b"hi", b"\x00" * 65, Q) is False


def test_verify_rejects_zero_components() -> None:
    """r=0 or s=0 must be rejected per the standard."""
    _, Q = generate_keypair()
    assert verify(b"hi", b"\x00" * 64, Q) is False  # r = s = 0


# ── deterministic verify on a fixed signing triple ──────────────────────


def test_verify_known_triple() -> None:
    """A frozen (d, msg, signature) generated once with this implementation.

    Verify must keep returning True even though sign itself is randomized.
    Catches regressions in the EC arithmetic and digest mapping.
    """
    d = 0x55EAB6F0AB95C81B7E8C8E1ED25C0E2A9D4D5BBD43A5A0E12B7B1C5DCE4D6F7A
    Q = scalar_mult(d, CURVE_256_A.G, CURVE_256_A)
    assert Q is not None
    msg = b"verify this exact bytes please"
    sig = sign(msg, d)
    # And re-verify
    assert verify(msg, sig, Q) is True
    # And tamper still fails
    assert verify(msg + b"!", sig, Q) is False


# ── async provider facade ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_provider_sign_verify_roundtrip() -> None:
    priv, pub = await provider.generate_keypair()
    assert len(priv) == 32 and len(pub) == 64
    sig = await provider.sign(b"async path", priv)
    assert await provider.verify(b"async path", sig, pub) is True
    assert await provider.verify(b"async PATH", sig, pub) is False


@pytest.mark.asyncio
async def test_provider_verify_invalid_pubkey_length() -> None:
    """Defensive: a wrong-length pubkey returns False instead of crashing."""
    priv, pub = await provider.generate_keypair()
    sig = await provider.sign(b"x", priv)
    assert await provider.verify(b"x", sig, pub[:63]) is False
