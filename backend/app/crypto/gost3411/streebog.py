"""GOST R 34.11-2012 (Streebog) hash function — optimized manual implementation.

Reference: RFC 6986. Two output sizes are exposed: 256-bit and 512-bit.

Vector convention: a 64-byte vector ``v`` is interpreted as a 512-bit number
in little-endian order (v[0] is the least significant byte) when it appears
inside the integer additions for ``N`` and ``Sigma``.

Performance notes
-----------------
Naive implementations of Streebog are dominated by the linear transform
``L``, which iterates 64 bits per 8-byte chunk and XORs the matrix rows
``A``. The standard optimization is to fuse S+P+L into eight 256-entry
lookup tables of 64-bit values: each input byte at position ``k`` of an
input block contributes ``T[k][PI[byte]]`` to one fixed output 64-bit
chunk, and chunks are independent. That replaces ~8200 bit-ops per block
with 64 lookups + 56 XORs.

The reference functions ``_S_ref``, ``_P_ref``, ``_L_ref`` and ``_LPS_ref``
are kept verbatim from the spec and only used by the startup self-test.
"""
from __future__ import annotations

import struct

from .constants import A, C, PI, TAU
from ..utils.bytes_ops import int_to_bytes_le, xor_bytes

_PACK64x8 = struct.Struct(">8Q").pack

_BLOCK = 64  # 512 bits


# ─────────────────────────── reference (spec-true) ─────────────────────────────

def _S_ref(x: bytes) -> bytes:
    return bytes(PI[b] for b in x)


def _P_ref(x: bytes) -> bytes:
    return bytes(x[TAU[i]] for i in range(_BLOCK))


def _L_ref(x: bytes) -> bytes:
    out = bytearray(_BLOCK)
    for i in range(8):
        v = int.from_bytes(x[i * 8:(i + 1) * 8], "big")
        r = 0
        for j in range(64):
            if v & (1 << (63 - j)):
                r ^= A[j]
        out[i * 8:(i + 1) * 8] = r.to_bytes(8, "big")
    return bytes(out)


def _LPS_ref(x: bytes) -> bytes:
    return _L_ref(_P_ref(_S_ref(x)))


# ───────────────────── fused S+P+L lookup table (T-table) ──────────────────────
#
# Derivation:
#   Let y = S(x), z = P(y), w = L(z).
#   z[i] = y[TAU[i]] = PI[x[TAU[i]]]
#   For output 8-byte chunk i, the linear transform L treats z[8i:8i+8] as a
#   64-bit big-endian integer V_i and produces XOR of A[bit] for each set bit.
#
#   Decompose V_i byte-by-byte: byte at position k inside the chunk contributes
#   8 high bits, bits (63 - k*8 .. 63 - k*8 - 7). The contribution of value `b`
#   placed at intra-chunk byte index k is:
#
#       row(k, b) = XOR_{bit=0..7 if b & (1 << (7-bit)) != 0} A[k*8 + bit]
#
#   So chunk i = XOR_{k=0..7} row(k, z[8i + k]).
#
#   Pre-folding S in: row_PI(k, b) = row(k, PI[b]).
#   Final input to chunk i is x[TAU[8i + k]] for k=0..7.

def _build_lps_tables() -> tuple[tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]]:
    rows = [[0] * 256 for _ in range(8)]
    for k in range(8):
        base = k * 8
        for b in range(256):
            r = 0
            for bit in range(8):
                if b & (1 << (7 - bit)):
                    r ^= A[base + bit]
            rows[k][b] = r
    # Fuse S (PI) into the lookup so we index by the *raw* input byte.
    fused = [[rows[k][PI[b]] for b in range(256)] for k in range(8)]
    return tuple(tuple(t) for t in rows), tuple(tuple(t) for t in fused)


_T_RAW, _T_PI = _build_lps_tables()


# Локальные привязки таблиц — обращение по имени модуля медленнее, чем
# к локальной переменной (важно для горячего цикла).
_t0, _t1, _t2, _t3, _t4, _t5, _t6, _t7 = _T_PI


def _LPS(x: bytes) -> bytes:
    """Optimized S+P+L через ``struct.pack(">8Q", ...)``.

    8 выходных 64-битных чанков пакуются в bytes одним C-вызовом, без
    промежуточных bigint-сдвигов и без множественных ``to_bytes``.
    """
    return _PACK64x8(
        _t0[x[TAU[0]]] ^ _t1[x[TAU[1]]] ^ _t2[x[TAU[2]]] ^ _t3[x[TAU[3]]]
        ^ _t4[x[TAU[4]]] ^ _t5[x[TAU[5]]] ^ _t6[x[TAU[6]]] ^ _t7[x[TAU[7]]],
        _t0[x[TAU[8]]] ^ _t1[x[TAU[9]]] ^ _t2[x[TAU[10]]] ^ _t3[x[TAU[11]]]
        ^ _t4[x[TAU[12]]] ^ _t5[x[TAU[13]]] ^ _t6[x[TAU[14]]] ^ _t7[x[TAU[15]]],
        _t0[x[TAU[16]]] ^ _t1[x[TAU[17]]] ^ _t2[x[TAU[18]]] ^ _t3[x[TAU[19]]]
        ^ _t4[x[TAU[20]]] ^ _t5[x[TAU[21]]] ^ _t6[x[TAU[22]]] ^ _t7[x[TAU[23]]],
        _t0[x[TAU[24]]] ^ _t1[x[TAU[25]]] ^ _t2[x[TAU[26]]] ^ _t3[x[TAU[27]]]
        ^ _t4[x[TAU[28]]] ^ _t5[x[TAU[29]]] ^ _t6[x[TAU[30]]] ^ _t7[x[TAU[31]]],
        _t0[x[TAU[32]]] ^ _t1[x[TAU[33]]] ^ _t2[x[TAU[34]]] ^ _t3[x[TAU[35]]]
        ^ _t4[x[TAU[36]]] ^ _t5[x[TAU[37]]] ^ _t6[x[TAU[38]]] ^ _t7[x[TAU[39]]],
        _t0[x[TAU[40]]] ^ _t1[x[TAU[41]]] ^ _t2[x[TAU[42]]] ^ _t3[x[TAU[43]]]
        ^ _t4[x[TAU[44]]] ^ _t5[x[TAU[45]]] ^ _t6[x[TAU[46]]] ^ _t7[x[TAU[47]]],
        _t0[x[TAU[48]]] ^ _t1[x[TAU[49]]] ^ _t2[x[TAU[50]]] ^ _t3[x[TAU[51]]]
        ^ _t4[x[TAU[52]]] ^ _t5[x[TAU[53]]] ^ _t6[x[TAU[54]]] ^ _t7[x[TAU[55]]],
        _t0[x[TAU[56]]] ^ _t1[x[TAU[57]]] ^ _t2[x[TAU[58]]] ^ _t3[x[TAU[59]]]
        ^ _t4[x[TAU[60]]] ^ _t5[x[TAU[61]]] ^ _t6[x[TAU[62]]] ^ _t7[x[TAU[63]]],
    )


def _xor64(a: bytes, b: bytes) -> bytes:
    """XOR two 64-byte buffers via bigint — much faster than per-byte zip."""
    return (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).to_bytes(_BLOCK, "big")


def _E(K: bytes, m: bytes) -> bytes:
    state = _xor64(K, m)
    for i in range(12):
        state = _LPS(state)
        K = _LPS(_xor64(K, C[i]))
        state = _xor64(state, K)
    return state


def _g(N: bytes, h: bytes, m: bytes) -> bytes:
    K = _LPS(_xor64(h, N))
    return _xor64(_xor64(_E(K, m), h), m)


def _hash(message: bytes, hash_size: int) -> bytes:
    if hash_size not in (256, 512):
        raise ValueError("hash_size must be 256 or 512")

    h = (b"\x01" if hash_size == 256 else b"\x00") * _BLOCK
    N = 0
    sigma = 0
    msg = bytes(message)

    while len(msg) >= _BLOCK:
        m = msg[-_BLOCK:]
        msg = msg[:-_BLOCK]
        h = _g(int_to_bytes_le(N, _BLOCK), h, m)
        N = (N + 512) & ((1 << 512) - 1)
        sigma = (sigma + int.from_bytes(m, "little")) & ((1 << 512) - 1)

    rem_len_bits = len(msg) * 8
    pad = b"\x00" * (_BLOCK - 1 - len(msg))
    m = pad + b"\x01" + msg
    h = _g(int_to_bytes_le(N, _BLOCK), h, m)
    N = (N + rem_len_bits) & ((1 << 512) - 1)
    sigma = (sigma + int.from_bytes(m, "little")) & ((1 << 512) - 1)

    h = _g(b"\x00" * _BLOCK, h, int_to_bytes_le(N, _BLOCK))
    h = _g(b"\x00" * _BLOCK, h, int_to_bytes_le(sigma, _BLOCK))

    if hash_size == 256:
        return h[:32]
    return h


def streebog_512(message: bytes) -> bytes:
    return _hash(message, 512)


def streebog_256(message: bytes) -> bytes:
    return _hash(message, 256)


# ─────────────────────────────── self-test ─────────────────────────────────
#
# Asserts that the optimized LPS produces bit-identical output to the
# reference S+P+L for a handful of inputs. Runs once at import time. If
# anything diverges, the module fails to load and the server can't start
# with a broken hash function.

def _hash_with_ref_LPS(message: bytes, hash_size: int) -> bytes:
    """Эталонная end-to-end реализация: использует _LPS_ref (битно идентична
    тому, что было в проекте до оптимизации). Используется только в self-test.
    """
    def _E_ref(K, m):
        state = xor_bytes(K, m)
        for i in range(12):
            state = _LPS_ref(state)
            K = _LPS_ref(xor_bytes(K, C[i]))
            state = xor_bytes(state, K)
        return state

    def _g_ref(N, h, m):
        K = _LPS_ref(xor_bytes(h, N))
        return xor_bytes(xor_bytes(_E_ref(K, m), h), m)

    h = (b"\x01" if hash_size == 256 else b"\x00") * _BLOCK
    N = 0
    sigma = 0
    msg = bytes(message)
    while len(msg) >= _BLOCK:
        m = msg[-_BLOCK:]
        msg = msg[:-_BLOCK]
        h = _g_ref(int_to_bytes_le(N, _BLOCK), h, m)
        N = (N + 512) & ((1 << 512) - 1)
        sigma = (sigma + int.from_bytes(m, "little")) & ((1 << 512) - 1)
    rem_len_bits = len(msg) * 8
    pad = b"\x00" * (_BLOCK - 1 - len(msg))
    m = pad + b"\x01" + msg
    h = _g_ref(int_to_bytes_le(N, _BLOCK), h, m)
    N = (N + rem_len_bits) & ((1 << 512) - 1)
    sigma = (sigma + int.from_bytes(m, "little")) & ((1 << 512) - 1)
    h = _g_ref(b"\x00" * _BLOCK, h, int_to_bytes_le(N, _BLOCK))
    h = _g_ref(b"\x00" * _BLOCK, h, int_to_bytes_le(sigma, _BLOCK))
    return h[:32] if hash_size == 256 else h


def _self_test() -> None:
    import os

    # 1. Низкоуровневая проверка LPS на нескольких блоках.
    cases = [b"\x00" * _BLOCK, b"\xff" * _BLOCK, bytes(range(_BLOCK))]
    cases.extend(os.urandom(_BLOCK) for _ in range(4))
    for x in cases:
        if _LPS(x) != _LPS_ref(x):
            raise RuntimeError(
                "Streebog optimized LPS diverges from reference — "
                "refusing to load with a broken hash."
            )

    # 2. End-to-end проверка hash против эталонной реализации, которая
    #    битно идентична доптимизационной (та же самая endian-конвенция
    #    для truncation, на которую завязан весь существующий ЭЦП и
    #    conversation-key).
    msgs = [b"", b"a", b"hello world", b"x" * 63, b"x" * 64, b"x" * 65,
            b"x" * 127, b"x" * 128, b"x" * 200, os.urandom(500)]
    for m in msgs:
        if streebog_256(m) != _hash_with_ref_LPS(m, 256):
            raise RuntimeError(
                "Streebog optimized streebog_256 diverges from reference "
                f"on input of length {len(m)} — refusing to load."
            )
        if streebog_512(m) != _hash_with_ref_LPS(m, 512):
            raise RuntimeError(
                "Streebog optimized streebog_512 diverges from reference "
                f"on input of length {len(m)} — refusing to load."
            )


_self_test()


# Backward compatibility for the rest of the codebase that may import
# the lowercase reference names. They now route to the optimized impl.
_S = _S_ref
_P = _P_ref
_L = _L_ref
