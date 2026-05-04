"""Affine-coordinate elliptic-curve arithmetic.

Point at infinity is represented as Python ``None``. We rely on
``pow(x, -1, p)`` (Python 3.8+) for modular inversion.
"""
from __future__ import annotations

from typing import Optional, Tuple

from .curves import Curve

Point = Optional[Tuple[int, int]]  # None == identity / point at infinity


def is_on_curve(P: Point, curve: Curve) -> bool:
    if P is None:
        return True
    x, y = P
    return (y * y - (x * x * x + curve.a * x + curve.b)) % curve.p == 0


def point_neg(P: Point, curve: Curve) -> Point:
    if P is None:
        return None
    x, y = P
    return (x, (-y) % curve.p)


def point_add(P: Point, Q: Point, curve: Curve) -> Point:
    if P is None:
        return Q
    if Q is None:
        return P
    x1, y1 = P
    x2, y2 = Q
    p = curve.p
    if x1 == x2:
        if (y1 + y2) % p == 0:
            return None
        # point doubling
        m = (3 * x1 * x1 + curve.a) * pow(2 * y1, -1, p) % p
    else:
        m = (y2 - y1) * pow(x2 - x1, -1, p) % p
    x3 = (m * m - x1 - x2) % p
    y3 = (m * (x1 - x3) - y1) % p
    return (x3, y3)


def scalar_mult(k: int, P: Point, curve: Curve) -> Point:
    """Double-and-add scalar multiplication. Not constant-time."""
    if P is None or k % curve.q == 0:
        return None
    if k < 0:
        return scalar_mult(-k, point_neg(P, curve), curve)
    R: Point = None
    Q: Point = P
    while k > 0:
        if k & 1:
            R = point_add(R, Q, curve)
        Q = point_add(Q, Q, curve)
        k >>= 1
    return R
