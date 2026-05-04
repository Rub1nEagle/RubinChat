"""GOST 34.10-2012 digital signature (sign / verify / keygen).

The signature is the concatenation r || s, each component zero-padded
on the left to ``ceil(log2(q)/8)`` bytes. The hash digest is the
Streebog-256 output of the message.
"""
from __future__ import annotations

import secrets
from typing import Tuple

from ..gost3411 import streebog_256
from .curves import CURVE_256_A, Curve
from .ec import scalar_mult, point_add

PublicKey = Tuple[int, int]
PrivateKey = int


def _component_size(curve: Curve) -> int:
    return (curve.q.bit_length() + 7) // 8


def _digest_to_alpha(digest: bytes, curve: Curve) -> int:
    alpha = int.from_bytes(digest, "big")
    e = alpha % curve.q
    return e if e != 0 else 1


def generate_keypair(curve: Curve = CURVE_256_A) -> tuple[PrivateKey, PublicKey]:
    """Return (d, Q) where d is the private scalar and Q = d*G."""
    d = secrets.randbelow(curve.q - 1) + 1
    Q = scalar_mult(d, curve.G, curve)
    assert Q is not None  # by construction
    return d, Q


def sign(message: bytes, private_key: PrivateKey, curve: Curve = CURVE_256_A) -> bytes:
    digest = streebog_256(message)
    e = _digest_to_alpha(digest, curve)
    while True:
        k = secrets.randbelow(curve.q - 1) + 1
        C = scalar_mult(k, curve.G, curve)
        if C is None:
            continue
        r = C[0] % curve.q
        if r == 0:
            continue
        s = (r * private_key + k * e) % curve.q
        if s == 0:
            continue
        size = _component_size(curve)
        return r.to_bytes(size, "big") + s.to_bytes(size, "big")


def verify(
    message: bytes,
    signature: bytes,
    public_key: PublicKey,
    curve: Curve = CURVE_256_A,
) -> bool:
    size = _component_size(curve)
    if len(signature) != 2 * size:
        return False
    r = int.from_bytes(signature[:size], "big")
    s = int.from_bytes(signature[size:], "big")
    if not (0 < r < curve.q and 0 < s < curve.q):
        return False
    digest = streebog_256(message)
    e = _digest_to_alpha(digest, curve)
    v = pow(e, -1, curve.q)
    z1 = (s * v) % curve.q
    z2 = (-r * v) % curve.q
    C1 = scalar_mult(z1, curve.G, curve)
    C2 = scalar_mult(z2, public_key, curve)
    C = point_add(C1, C2, curve)
    if C is None:
        return False
    return (C[0] % curve.q) == r
