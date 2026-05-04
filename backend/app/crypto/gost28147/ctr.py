"""CTR mode wrapper around GOST 28147 ECB.

The 8-byte counter is initialized from the 8-byte nonce and incremented
as a big-endian integer between blocks. Encryption and decryption are
the same XOR-with-keystream operation.

Performance notes
-----------------
1. Subkeys are expanded once per call (instead of once per block).
2. The 32 Feistel rounds are inlined into the keystream loop, with the
   round-function tables and subkeys bound to local names — Python
   resolves locals faster than module-level globals.
3. The keystream is built into a bytearray, then XOR-combined with the
   data via ``int.from_bytes`` ⊕ ``int.to_bytes``. Those are C-level
   operations and saturate memory bandwidth, so XOR over hundreds of
   kilobytes is essentially free compared to a per-byte Python loop.
"""
from __future__ import annotations

import struct

from .cipher import _T0, _T1, _T2, _T3, expand_key

_BLOCK = 8
_MASK32 = 0xFFFFFFFF
_MASK64 = (1 << 64) - 1
_PACK_Q = struct.Struct(">Q").pack


def ctr_crypt(data: bytes, key: bytes, nonce: bytes) -> bytes:
    if len(nonce) != _BLOCK:
        raise ValueError("nonce must be 8 bytes")
    if not data:
        return b""

    s0, s1, s2, s3, s4, s5, s6, s7 = expand_key(key)
    # Локальные привязки таблиц — обращение к локальной переменной быстрее.
    T0, T1, T2, T3 = _T0, _T1, _T2, _T3
    MASK32 = _MASK32

    counter = int.from_bytes(nonce, "big")
    n_full, tail = divmod(len(data), _BLOCK)
    n_blocks = n_full + (1 if tail else 0)

    ks = bytearray(n_blocks * _BLOCK)

    for i in range(n_blocks):
        # Counter → n1 (high 32 bits) || n2 (low 32 bits).
        n1 = (counter >> 32) & MASK32
        n2 = counter & MASK32

        # 32 Feistel rounds, key schedule (s0..s7) ×3 + (s7..s0).
        # Раскручены ровно настолько, чтобы убрать оверхед на индексирование
        # в кортеже подключей.
        # rounds 1..8 ----------------------------------------------------
        s = (n1 + s0) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s1) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s2) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s3) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s4) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s5) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s6) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s7) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        # rounds 9..16 ---------------------------------------------------
        s = (n1 + s0) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s1) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s2) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s3) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s4) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s5) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s6) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s7) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        # rounds 17..24 --------------------------------------------------
        s = (n1 + s0) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s1) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s2) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s3) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s4) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s5) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s6) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s7) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        # rounds 25..32 (reverse) ----------------------------------------
        s = (n1 + s7) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s6) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s5) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s4) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s3) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s2) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s1) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        s = (n1 + s0) & MASK32
        n1, n2 = (n2 ^ (T0[s & 0xFF] ^ T1[(s >> 8) & 0xFF] ^ T2[(s >> 16) & 0xFF] ^ T3[(s >> 24) & 0xFF])) & MASK32, n1
        # output halves are written reversed (per spec).
        ks[i * _BLOCK:i * _BLOCK + _BLOCK] = _PACK_Q((n2 << 32) | n1)
        counter = (counter + 1) & _MASK64

    n = len(data)
    ct_int = int.from_bytes(data, "big") ^ int.from_bytes(bytes(ks[:n]), "big")
    return ct_int.to_bytes(n, "big")
