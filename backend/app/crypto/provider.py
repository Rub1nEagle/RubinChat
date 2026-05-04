"""Single async-friendly facade over the three GOST primitives.

Heavy operations (scalar multiplication for sign/verify, Streebog
compression) are CPU-bound, so we offload them via
``asyncio.to_thread`` to avoid blocking the event loop.

Key encoding used everywhere on the wire:

* private key  -> 32-byte big-endian scalar
* public key   -> 64 bytes: x || y, each 32-byte big-endian
* signature    -> 64 bytes: r || s, each 32-byte big-endian
* hash digest  -> 32-byte Streebog-256
"""
from __future__ import annotations

import asyncio
import secrets

from .gost28147 import ctr_crypt
from .gost3410 import CURVE_256_A, generate_keypair, sign, verify
from .gost3411 import streebog_256


class CryptoProvider:
    """Async facade over the project's manual GOST primitives."""

    def __init__(self) -> None:
        self.curve = CURVE_256_A
        self._scalar_size = (self.curve.q.bit_length() + 7) // 8

    # ------------------------------------------------------------------
    # key material
    # ------------------------------------------------------------------
    async def generate_keypair(self) -> tuple[bytes, bytes]:
        d, Q = await asyncio.to_thread(generate_keypair, self.curve)
        priv = d.to_bytes(self._scalar_size, "big")
        pub = Q[0].to_bytes(self._scalar_size, "big") + Q[1].to_bytes(self._scalar_size, "big")
        return priv, pub

    # ------------------------------------------------------------------
    # signature
    # ------------------------------------------------------------------
    async def sign(self, data: bytes, private_key: bytes) -> bytes:
        d = int.from_bytes(private_key, "big")
        return await asyncio.to_thread(sign, data, d, self.curve)

    async def verify(self, data: bytes, signature: bytes, public_key: bytes) -> bool:
        if len(public_key) != 2 * self._scalar_size:
            return False
        x = int.from_bytes(public_key[: self._scalar_size], "big")
        y = int.from_bytes(public_key[self._scalar_size:], "big")
        return await asyncio.to_thread(verify, data, signature, (x, y), self.curve)

    # ------------------------------------------------------------------
    # symmetric encryption (GOST 28147 in CTR mode)
    # ------------------------------------------------------------------
    @staticmethod
    def random_nonce() -> bytes:
        return secrets.token_bytes(8)

    @staticmethod
    def random_session_key() -> bytes:
        return secrets.token_bytes(32)

    async def encrypt(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        return await asyncio.to_thread(ctr_crypt, data, key, nonce)

    async def decrypt(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        # CTR decrypt is the same as encrypt.
        return await asyncio.to_thread(ctr_crypt, data, key, nonce)

    # ------------------------------------------------------------------
    # hash
    # ------------------------------------------------------------------
    async def hash(self, data: bytes) -> bytes:
        return await asyncio.to_thread(streebog_256, data)


provider = CryptoProvider()
