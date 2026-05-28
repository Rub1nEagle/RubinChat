"""Deterministic conversation key shared between two users.

Чисто учебный шорткат: Streebog-256 от строки `gost-demo-conv:lo:hi`,
где lo/hi — отсортированные id пользователей. Тот же ключ выводят и
текстовые routes (`/api/crypto/seal`/`/unseal`), и сервис вложений —
поэтому картинки и тексты в одном диалоге шифруются на одном ключе.
"""
from __future__ import annotations

from .provider import provider


def conversation_key_material(a: int, b: int) -> bytes:
    lo, hi = sorted((a, b))
    return f"gost-demo-conv:{lo}:{hi}".encode("utf-8")


async def conversation_key(a: int, b: int) -> bytes:
    return await provider.hash(conversation_key_material(a, b))
