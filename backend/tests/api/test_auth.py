"""Auth flow integration tests.

Cover the full registration / login / change-password / delete-account
loop end-to-end through the FastAPI app, using a sqlite-backed test DB
(see conftest). The crypto provider is the real one — every register
generates a GOST 34.10 keypair, every login decrypts the private key
under a key derived via Streebog from the password.
"""
from __future__ import annotations

import pytest


# ── register ─────────────────────────────────────────────────────────────


async def test_register_success_returns_token_and_private_key(client) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass1!"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "alice"
    assert body["user_id"] >= 1
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
    # Private key returned as 64 hex chars (32 raw bytes for paramSetA).
    assert len(body["private_key_hex"]) == 64
    bytes.fromhex(body["private_key_hex"])  # parses cleanly


async def test_register_rejects_duplicate_username(client, register_user) -> None:
    await register_user(username="bob", password="bobpass123!")
    resp = await client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "anotherpass!"},
    )
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "username,password",
    [
        ("ab", "longenoughpass"),       # username too short
        ("a" * 65, "longenoughpass"),   # username too long
        ("with space", "longenough!!"),  # invalid charset
        ("alice", "short"),             # password too short (<8)
    ],
)
async def test_register_rejects_invalid_payload(client, username, password) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 422


# ── login ────────────────────────────────────────────────────────────────


async def test_login_success_after_register(client, register_user) -> None:
    user = await register_user(username="carol", password="carolpass1!")
    resp = await client.post(
        "/api/auth/login",
        json={"username": "carol", "password": "carolpass1!"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == user["user_id"]
    # Login must return the SAME private key that registration did,
    # otherwise existing signatures would stop verifying.
    assert body["private_key_hex"] == user["private_key_hex"]


async def test_login_wrong_password_rejected(client, register_user) -> None:
    await register_user(username="dave", password="davepass123!")
    resp = await client.post(
        "/api/auth/login",
        json={"username": "dave", "password": "WRONGpass123!"},
    )
    assert resp.status_code == 401


async def test_login_unknown_user_rejected(client) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "whateverpass1!"},
    )
    assert resp.status_code == 401


# ── change password ──────────────────────────────────────────────────────


async def test_change_password_re_wraps_private_key(client, register_user) -> None:
    user = await register_user(username="eve", password="oldpassword1!")
    # Change password
    resp = await client.post(
        "/api/auth/change-password",
        headers=user["headers"],
        json={"current_password": "oldpassword1!", "new_password": "newpassword1!"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Private key material must remain unchanged (only its wrapper changes).
    assert body["private_key_hex"] == user["private_key_hex"]

    # Old password no longer works
    resp = await client.post(
        "/api/auth/login",
        json={"username": "eve", "password": "oldpassword1!"},
    )
    assert resp.status_code == 401

    # New password does
    resp = await client.post(
        "/api/auth/login",
        json={"username": "eve", "password": "newpassword1!"},
    )
    assert resp.status_code == 200
    assert resp.json()["private_key_hex"] == user["private_key_hex"]


async def test_change_password_wrong_current_rejected(client, register_user) -> None:
    user = await register_user(username="frank", password="frankpass123!")
    resp = await client.post(
        "/api/auth/change-password",
        headers=user["headers"],
        json={"current_password": "WRONGcurrent!", "new_password": "newpass123!"},
    )
    assert resp.status_code == 401


async def test_change_password_same_new_rejected(client, register_user) -> None:
    user = await register_user(username="grace", password="gracepass123!")
    resp = await client.post(
        "/api/auth/change-password",
        headers=user["headers"],
        json={"current_password": "gracepass123!", "new_password": "gracepass123!"},
    )
    assert resp.status_code == 400


# ── delete account ───────────────────────────────────────────────────────


async def test_delete_account_success(client, register_user) -> None:
    user = await register_user(username="harry", password="harrypass123!")
    resp = await client.post(
        "/api/auth/delete-account",
        headers=user["headers"],
        json={"password": "harrypass123!"},
    )
    assert resp.status_code == 204
    # Login afterwards fails because the user is gone.
    resp = await client.post(
        "/api/auth/login",
        json={"username": "harry", "password": "harrypass123!"},
    )
    assert resp.status_code == 401


async def test_delete_account_wrong_password_rejected(client, register_user) -> None:
    user = await register_user(username="ivy", password="ivypass123!")
    resp = await client.post(
        "/api/auth/delete-account",
        headers=user["headers"],
        json={"password": "WRONG"},
    )
    assert resp.status_code == 401


async def test_protected_route_requires_token(client) -> None:
    resp = await client.get("/api/users/me")
    assert resp.status_code == 401
    resp = await client.get("/api/users/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


async def test_me_returns_profile_for_authenticated_user(client, register_user) -> None:
    user = await register_user(username="jack", password="jackpass123!")
    resp = await client.get("/api/users/me", headers=user["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "jack"
    assert body["user_id"] == user["user_id"]
    assert body["public_key_hex"]  # 64-byte pubkey -> 128 hex chars
    assert len(body["public_key_hex"]) == 128
