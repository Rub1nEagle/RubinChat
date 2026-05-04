"""Tiny byte / integer helpers shared by every crypto module."""
from __future__ import annotations


def xor_bytes(a: bytes, b: bytes) -> bytes:
    if len(a) != len(b):
        raise ValueError("xor_bytes: length mismatch")
    return bytes(x ^ y for x, y in zip(a, b))


def int_to_bytes_be(n: int, length: int) -> bytes:
    return n.to_bytes(length, "big")


def int_to_bytes_le(n: int, length: int) -> bytes:
    return n.to_bytes(length, "little")


def bytes_to_int_be(b: bytes) -> int:
    return int.from_bytes(b, "big")


def bytes_to_int_le(b: bytes) -> int:
    return int.from_bytes(b, "little")
