"""Crypto helper routes — pure transformation endpoints (no persistence).

These are the bridge between the vanilla-JS frontend and the manual
GOST primitives. The route layer doesn't perform crypto itself; it
delegates to the ``CryptoProvider`` and to two tiny pure helpers below.

For pedagogical simplicity, the conversation key is derived
deterministically from the (sorted) user IDs via Streebog-256. This
is documented as a teaching shortcut in README.md and is NOT real
end-to-end encryption.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...crypto.conversation import conversation_key as _conversation_key  # re-export
from ...crypto.conversation import conversation_key_material as _conversation_key_material  # re-export
from ...crypto.provider import provider
from ...database.session import get_db
from ...models import User
from ...services import user as user_service
from ..deps import current_user

router = APIRouter()


class SealRequest(BaseModel):
    recipient_id: int
    # 8 000 символов с запасом покрывают типичные сообщения и кириллицу
    # (UTF-8 → 2 байта/символ → 16 КБ → 32 000 hex < 64 000 max в MessageCreate).
    plaintext: str = Field(min_length=1, max_length=8000)
    sender_private_key_hex: str = Field(min_length=64, max_length=64)


class SealResponse(BaseModel):
    encrypted_payload_hex: str
    nonce_hex: str
    signature_hex: str


class UnsealRequest(BaseModel):
    sender_id: int
    recipient_id: int
    encrypted_payload_hex: str
    nonce_hex: str = Field(min_length=16, max_length=16)
    signature_hex: str = Field(min_length=128, max_length=128)


class UnsealResponse(BaseModel):
    plaintext: str
    signature_valid: bool


class UnsealBatchRequest(BaseModel):
    items: list[UnsealRequest]


class UnsealBatchResponse(BaseModel):
    results: list[UnsealResponse]


@router.post("/seal", response_model=SealResponse)
async def seal(
    payload: SealRequest,
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> SealResponse:
    if payload.recipient_id == me.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot send to self")
    recipient = await user_service.get_by_id(session, payload.recipient_id)
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="recipient not found")

    try:
        priv = bytes.fromhex(payload.sender_private_key_hex)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad private key") from exc

    key = await _conversation_key(me.id, recipient.id)
    nonce = provider.random_nonce()
    encrypted = await provider.encrypt(payload.plaintext.encode("utf-8"), key, nonce)
    signature = await provider.sign(encrypted + nonce, priv)
    return SealResponse(
        encrypted_payload_hex=encrypted.hex(),
        nonce_hex=nonce.hex(),
        signature_hex=signature.hex(),
    )


async def _unseal_one(
    item: UnsealRequest,
    *,
    me_id: int,
    sender_pubkey_cache: dict[int, bytes],
    convkey_cache: dict[tuple[int, int], bytes],
    session: AsyncSession,
) -> UnsealResponse:
    if me_id not in (item.sender_id, item.recipient_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="caller is not a participant of this conversation",
        )

    pubkey = sender_pubkey_cache.get(item.sender_id)
    if pubkey is None:
        sender = await user_service.get_by_id(session, item.sender_id)
        if sender is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sender not found")
        pubkey = sender.public_key
        sender_pubkey_cache[item.sender_id] = pubkey

    try:
        encrypted = bytes.fromhex(item.encrypted_payload_hex)
        nonce = bytes.fromhex(item.nonce_hex)
        signature = bytes.fromhex(item.signature_hex)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad hex input") from exc

    valid = await provider.verify(encrypted + nonce, signature, pubkey)

    pair = tuple(sorted((item.sender_id, item.recipient_id)))
    key = convkey_cache.get(pair)
    if key is None:
        key = await _conversation_key(item.sender_id, item.recipient_id)
        convkey_cache[pair] = key

    plaintext_bytes = await provider.decrypt(encrypted, key, nonce)
    try:
        plaintext = plaintext_bytes.decode("utf-8")
    except UnicodeDecodeError:
        plaintext = plaintext_bytes.hex()
    return UnsealResponse(plaintext=plaintext, signature_valid=valid)


@router.post("/unseal", response_model=UnsealResponse)
async def unseal(
    payload: UnsealRequest,
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> UnsealResponse:
    return await _unseal_one(
        payload,
        me_id=me.id,
        sender_pubkey_cache={},
        convkey_cache={},
        session=session,
    )


class FingerprintResponse(BaseModel):
    fingerprint_hex: str


@router.get("/fingerprint/{peer_id}", response_model=FingerprintResponse)
async def fingerprint(
    peer_id: int,
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> FingerprintResponse:
    """Совместный «safety number» как в Signal.

    Берём оба публичных ключа, сортируем по hex и хешируем Streebog-256.
    Обе стороны разговора видят один и тот же отпечаток — поэтому его
    можно сравнить голосом и убедиться, что MITM не подменил ключи.
    """
    if peer_id == me.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self fingerprint")
    peer = await user_service.get_by_id(session, peer_id)
    if peer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="peer not found")
    a = me.public_key.hex()
    b = peer.public_key.hex()
    pair = (a + b) if a <= b else (b + a)
    digest = await provider.hash(pair.encode("ascii"))
    return FingerprintResponse(fingerprint_hex=digest.hex())


@router.post("/unseal-batch", response_model=UnsealBatchResponse)
async def unseal_batch(
    payload: UnsealBatchRequest,
    session: AsyncSession = Depends(get_db),
    me: User = Depends(current_user),
) -> UnsealBatchResponse:
    """Расшифровать сразу несколько сообщений одним HTTP-запросом.

    Кэширует публичный ключ отправителя и ключ беседы внутри одного
    запроса, чтобы не ходить в БД и не пересчитывать Streebog для
    каждого сообщения.
    """
    if not payload.items:
        return UnsealBatchResponse(results=[])
    if len(payload.items) > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="batch is limited to 200 items",
        )
    sender_pubkey_cache: dict[int, bytes] = {}
    convkey_cache: dict[tuple[int, int], bytes] = {}
    results: list[UnsealResponse] = []
    for item in payload.items:
        results.append(
            await _unseal_one(
                item,
                me_id=me.id,
                sender_pubkey_cache=sender_pubkey_cache,
                convkey_cache=convkey_cache,
                session=session,
            )
        )
    return UnsealBatchResponse(results=results)
