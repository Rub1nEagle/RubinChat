"""Elliptic curve domain parameters used by GOST 34.10-2012.

Only one parameter set is included (id-tc26-gost-3410-2012-256-paramSetA
from RFC 7836). It is sufficient for an academic prototype and keeps
the surface small.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Curve:
    """Short Weierstrass curve y^2 = x^3 + a*x + b over F_p."""

    name: str
    p: int    # prime field modulus
    a: int    # curve coefficient a
    b: int    # curve coefficient b
    q: int    # subgroup order
    gx: int   # generator x
    gy: int   # generator y

    @property
    def G(self) -> tuple[int, int]:
        return (self.gx, self.gy)


# id-tc26-gost-3410-2012-256-paramSetA (RFC 7836)
CURVE_256_A = Curve(
    name="id-tc26-gost-3410-2012-256-paramSetA",
    p=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFD97,
    a=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFD94,
    b=0x00000000000000000000000000000000000000000000000000000000000000A6,
    q=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF6C611070995AD10045841B09B761B893,
    gx=0x0000000000000000000000000000000000000000000000000000000000000001,
    gy=0x8D91E471E0989CDA27DF505A453F2B7635294F2DDF23E3B122ACC99C9E9F1E14,
)
