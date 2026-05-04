"""WebSocket endpoint tests.

We use `fastapi.testclient.TestClient` (sync, ASGI in-process) for the WS
side because Starlette's WS test transport is the path-of-least-resistance
for in-process unit tests. The HTTP registration calls go through the same
TestClient to keep everything in one thread / one event loop, avoiding
cross-thread mishaps with the StaticPool sqlite engine.

The autouse `_patch_db` and `_reset_global_state` fixtures from conftest
still apply, so the DB and the in-memory connection registry start clean
for each test.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def sync_client(app):
    with TestClient(app) as c:
        yield c


def _register(sync_client, username: str, password: str = "passw0rd123!"):
    resp = sync_client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _seal(sync_client, sender, recipient_id: int, plaintext: str):
    resp = sync_client.post(
        "/api/crypto/seal",
        headers={"Authorization": f"Bearer {sender['access_token']}"},
        json={
            "recipient_id": recipient_id,
            "plaintext": plaintext,
            "sender_private_key_hex": sender["private_key_hex"],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── auth on the WS endpoint ──────────────────────────────────────────────


def test_ws_rejects_invalid_token(sync_client) -> None:
    """A bad JWT must fail policy-violation close (1008) instead of opening."""
    with pytest.raises(Exception):
        # Starlette raises WebSocketDisconnect (or similar) on close.
        with sync_client.websocket_connect("/ws?token=not-a-jwt"):
            pass


def test_ws_accepts_valid_token(sync_client) -> None:
    user = _register(sync_client, "alice")
    with sync_client.websocket_connect(f"/ws?token={user['access_token']}") as ws:
        # The server doesn't push anything on connect — it just accepts.
        # Round-trip a no-op typing event with a peer that doesn't exist;
        # the server silently drops it (no recipient online), no error
        # comes back, but the connection stays open.
        ws.send_json({"type": "typing", "peer_id": 99999, "kind": "text"})
        # If we got here without a disconnect, the connection is healthy.


# ── send via WS ──────────────────────────────────────────────────────────


def test_ws_send_returns_ack(sync_client) -> None:
    """Sending a sealed envelope over WS produces a `type=ack` reply."""
    alice = _register(sync_client, "alice")
    bob = _register(sync_client, "bob")
    sealed = _seal(sync_client, alice, bob["user_id"], "hello via ws")

    with sync_client.websocket_connect(f"/ws?token={alice['access_token']}") as ws:
        ws.send_json(
            {
                "type": "send",
                "payload": {
                    "recipient_id": bob["user_id"],
                    "encrypted_payload_hex": sealed["encrypted_payload_hex"],
                    "nonce_hex": sealed["nonce_hex"],
                    "signature_hex": sealed["signature_hex"],
                },
            }
        )
        ack = ws.receive_json()
        assert ack["type"] == "ack"
        assert ack["message"]["sender_id"] == alice["user_id"]
        assert ack["message"]["recipient_id"] == bob["user_id"]


def test_ws_unknown_type_returns_error(sync_client) -> None:
    user = _register(sync_client, "alice")
    with sync_client.websocket_connect(f"/ws?token={user['access_token']}") as ws:
        ws.send_json({"type": "unknown-op"})
        reply = ws.receive_json()
        assert reply["type"] == "error"


def test_ws_invalid_payload_returns_error(sync_client) -> None:
    """A `send` with a malformed payload must produce an error envelope,
    not crash the socket."""
    user = _register(sync_client, "alice")
    with sync_client.websocket_connect(f"/ws?token={user['access_token']}") as ws:
        ws.send_json({"type": "send", "payload": {"recipient_id": "not-an-int"}})
        reply = ws.receive_json()
        assert reply["type"] == "error"


# ── delivery to recipient ────────────────────────────────────────────────


def test_ws_delivers_message_to_recipient(sync_client) -> None:
    """When alice POSTs over WS, bob (connected) receives a delivery envelope."""
    alice = _register(sync_client, "alice")
    bob = _register(sync_client, "bob")
    sealed = _seal(sync_client, alice, bob["user_id"], "delivery test")

    with sync_client.websocket_connect(f"/ws?token={bob['access_token']}") as bob_ws:
        # Bob is now online (pre-existing presence broadcasts to nobody — alice
        # isn't connected yet, so we ignore any ambient frame).
        with sync_client.websocket_connect(f"/ws?token={alice['access_token']}") as alice_ws:
            # Alice's connect triggers a presence broadcast to bob.
            presence = bob_ws.receive_json()
            assert presence["type"] == "presence"
            assert presence["user_id"] == alice["user_id"]
            assert presence["is_online"] is True

            # Alice sends a message via the HTTP route (deliver fans out via
            # the same connection manager as the WS-send path).
            resp = sync_client.post(
                "/api/messages/",
                headers={"Authorization": f"Bearer {alice['access_token']}"},
                json={
                    "recipient_id": bob["user_id"],
                    "encrypted_payload_hex": sealed["encrypted_payload_hex"],
                    "nonce_hex": sealed["nonce_hex"],
                    "signature_hex": sealed["signature_hex"],
                },
            )
            assert resp.status_code == 201

            envelope = bob_ws.receive_json()
            assert envelope["type"] == "delivery"
            assert envelope["message"]["sender_id"] == alice["user_id"]
            assert envelope["message"]["recipient_id"] == bob["user_id"]
