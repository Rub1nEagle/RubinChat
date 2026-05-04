"""Message lifecycle tests over the full HTTP API.

The seal/unseal helpers go through the real `/api/crypto/seal` endpoint
so that signatures are produced exactly the way the live frontend does
(and so we never duplicate crypto code in tests).

Coverage:
* send + list + read with `peer_id` filter
* pagination via `before_id` cursor (regression for the 200-limit bug
  the user spotted in manual testing)
* edit: only sender can edit; on success delivers an updated payload
* delete: only sender can delete; afterwards the message is gone
* unseal-batch limit
"""
from __future__ import annotations


# ── helpers ──────────────────────────────────────────────────────────────


async def _seal(client, sender, recipient_id, plaintext):
    """Encrypt + sign a message via the crypto helper route — same code
    path the live frontend uses, so we never re-implement signing logic.
    """
    resp = await client.post(
        "/api/crypto/seal",
        headers=sender["headers"],
        json={
            "recipient_id": recipient_id,
            "plaintext": plaintext,
            "sender_private_key_hex": sender["private_key_hex"],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _send(client, sender, recipient_id, plaintext):
    sealed = await _seal(client, sender, recipient_id, plaintext)
    resp = await client.post(
        "/api/messages/",
        headers=sender["headers"],
        json={
            "recipient_id": recipient_id,
            "encrypted_payload_hex": sealed["encrypted_payload_hex"],
            "nonce_hex": sealed["nonce_hex"],
            "signature_hex": sealed["signature_hex"],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── send / receive / list ────────────────────────────────────────────────


async def test_send_and_list_messages(client, two_users) -> None:
    alice, bob = two_users
    msg = await _send(client, alice, bob["user_id"], "hi bob")
    assert msg["sender_id"] == alice["user_id"]
    assert msg["recipient_id"] == bob["user_id"]

    # Recipient sees the message in their list.
    resp = await client.get(
        "/api/messages/",
        headers=bob["headers"],
        params={"peer_id": alice["user_id"]},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == msg["id"]


async def test_unseal_returns_original_plaintext(client, two_users) -> None:
    alice, bob = two_users
    msg = await _send(client, alice, bob["user_id"], "secret payload")
    resp = await client.post(
        "/api/crypto/unseal",
        headers=bob["headers"],
        json={
            "sender_id": alice["user_id"],
            "recipient_id": bob["user_id"],
            "encrypted_payload_hex": msg["encrypted_payload_hex"],
            "nonce_hex": msg["nonce_hex"],
            "signature_hex": msg["signature_hex"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["plaintext"] == "secret payload"
    assert body["signature_valid"] is True


async def test_send_to_nonexistent_recipient_rejected(client, two_users) -> None:
    alice, bob = two_users
    # Seal targets a real recipient so the helper accepts it; we then
    # re-aim the envelope at a non-existent user_id. The route looks up
    # the recipient before checking the signature, so we hit "recipient
    # does not exist" with status 400.
    sealed = await _seal(client, alice, bob["user_id"], "x")
    resp = await client.post(
        "/api/messages/",
        headers=alice["headers"],
        json={
            "recipient_id": 99_999,
            "encrypted_payload_hex": sealed["encrypted_payload_hex"],
            "nonce_hex": sealed["nonce_hex"],
            "signature_hex": sealed["signature_hex"],
        },
    )
    assert resp.status_code == 400


async def test_send_with_invalid_signature_rejected(client, two_users) -> None:
    alice, bob = two_users
    sealed = await _seal(client, alice, bob["user_id"], "hi")
    # Flip a byte in the signature.
    bad_sig = bytearray(bytes.fromhex(sealed["signature_hex"]))
    bad_sig[0] ^= 0x01
    resp = await client.post(
        "/api/messages/",
        headers=alice["headers"],
        json={
            "recipient_id": bob["user_id"],
            "encrypted_payload_hex": sealed["encrypted_payload_hex"],
            "nonce_hex": sealed["nonce_hex"],
            "signature_hex": bad_sig.hex(),
        },
    )
    assert resp.status_code == 400


async def test_replay_same_nonce_rejected(client, two_users) -> None:
    """Re-submitting the exact same envelope must hit the anti-replay cache."""
    alice, bob = two_users
    sealed = await _seal(client, alice, bob["user_id"], "first time")
    payload = {
        "recipient_id": bob["user_id"],
        "encrypted_payload_hex": sealed["encrypted_payload_hex"],
        "nonce_hex": sealed["nonce_hex"],
        "signature_hex": sealed["signature_hex"],
    }
    r1 = await client.post("/api/messages/", headers=alice["headers"], json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/messages/", headers=alice["headers"], json=payload)
    assert r2.status_code == 400


# ── pagination ───────────────────────────────────────────────────────────


async def test_default_limit_returns_last_n_messages(client, two_users) -> None:
    """Without before_id cursor, the latest N messages come back in asc order."""
    alice, bob = two_users
    sent_ids = []
    for i in range(5):
        msg = await _send(client, alice, bob["user_id"], f"msg-{i}")
        sent_ids.append(msg["id"])

    resp = await client.get(
        "/api/messages/",
        headers=bob["headers"],
        params={"peer_id": alice["user_id"], "limit": 3},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 3
    # Last 3 messages, asc by id.
    assert [m["id"] for m in items] == sent_ids[-3:]


async def test_pagination_with_before_id_returns_older_window(client, two_users) -> None:
    """Cursor scrolling: ?before_id=X returns the limit messages strictly
    older than X. Catches the regression from the 200-limit bug we hit in
    manual testing.
    """
    alice, bob = two_users
    sent_ids = []
    for i in range(10):
        m = await _send(client, alice, bob["user_id"], f"msg-{i}")
        sent_ids.append(m["id"])

    # Grab the latest 4 first.
    resp = await client.get(
        "/api/messages/",
        headers=bob["headers"],
        params={"peer_id": alice["user_id"], "limit": 4},
    )
    latest = resp.json()
    assert [m["id"] for m in latest] == sent_ids[-4:]

    # Now scroll up: ask for the 4 messages older than the oldest of the latest batch.
    cursor = latest[0]["id"]
    resp = await client.get(
        "/api/messages/",
        headers=bob["headers"],
        params={"peer_id": alice["user_id"], "limit": 4, "before_id": cursor},
    )
    older = resp.json()
    assert [m["id"] for m in older] == sent_ids[-8:-4]
    # And every id in the older window is strictly less than the cursor.
    assert all(m["id"] < cursor for m in older)


async def test_limit_caps_at_500(client, two_users) -> None:
    """The ``limit`` query param has an upper bound so a malicious client
    can't DoS the backend by asking for everything in one go.
    """
    alice, bob = two_users
    resp = await client.get(
        "/api/messages/",
        headers=bob["headers"],
        params={"peer_id": alice["user_id"], "limit": 10_000},
    )
    assert resp.status_code == 422  # validation error from le=500


# ── edit ─────────────────────────────────────────────────────────────────


async def test_edit_message_success(client, two_users) -> None:
    alice, bob = two_users
    msg = await _send(client, alice, bob["user_id"], "before edit")
    sealed = await _seal(client, alice, bob["user_id"], "after edit")
    resp = await client.patch(
        f"/api/messages/{msg['id']}",
        headers=alice["headers"],
        json={
            "encrypted_payload_hex": sealed["encrypted_payload_hex"],
            "nonce_hex": sealed["nonce_hex"],
            "signature_hex": sealed["signature_hex"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == msg["id"]
    assert body["edited_at"] is not None
    assert body["encrypted_payload_hex"] == sealed["encrypted_payload_hex"]


async def test_edit_message_only_sender_allowed(client, two_users) -> None:
    alice, bob = two_users
    msg = await _send(client, alice, bob["user_id"], "alice's message")
    # Bob (recipient) tries to edit it.
    sealed = await _seal(client, bob, alice["user_id"], "bob's edit")
    resp = await client.patch(
        f"/api/messages/{msg['id']}",
        headers=bob["headers"],
        json={
            "encrypted_payload_hex": sealed["encrypted_payload_hex"],
            "nonce_hex": sealed["nonce_hex"],
            "signature_hex": sealed["signature_hex"],
        },
    )
    assert resp.status_code == 403


async def test_edit_nonexistent_message_404(client, two_users) -> None:
    alice, bob = two_users
    sealed = await _seal(client, alice, bob["user_id"], "x")
    resp = await client.patch(
        "/api/messages/99999",
        headers=alice["headers"],
        json={
            "encrypted_payload_hex": sealed["encrypted_payload_hex"],
            "nonce_hex": sealed["nonce_hex"],
            "signature_hex": sealed["signature_hex"],
        },
    )
    assert resp.status_code == 404


# ── delete ───────────────────────────────────────────────────────────────


async def test_delete_message_success(client, two_users) -> None:
    alice, bob = two_users
    msg = await _send(client, alice, bob["user_id"], "to be deleted")
    resp = await client.delete(
        f"/api/messages/{msg['id']}",
        headers=alice["headers"],
    )
    assert resp.status_code == 204

    # Subsequent listing must not include it.
    resp = await client.get(
        "/api/messages/",
        headers=bob["headers"],
        params={"peer_id": alice["user_id"]},
    )
    assert resp.status_code == 200
    assert all(m["id"] != msg["id"] for m in resp.json())


async def test_delete_message_only_sender_allowed(client, two_users) -> None:
    alice, bob = two_users
    msg = await _send(client, alice, bob["user_id"], "alice's message")
    resp = await client.delete(
        f"/api/messages/{msg['id']}",
        headers=bob["headers"],
    )
    assert resp.status_code == 403


# ── read receipts ────────────────────────────────────────────────────────


async def test_mark_read_updates_read_at(client, two_users) -> None:
    alice, bob = two_users
    await _send(client, alice, bob["user_id"], "hello")
    await _send(client, alice, bob["user_id"], "are you there?")
    resp = await client.post(
        "/api/messages/read",
        headers=bob["headers"],
        params={"peer_id": alice["user_id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    # Now the messages from alice → bob have read_at set.
    resp = await client.get(
        "/api/messages/",
        headers=bob["headers"],
        params={"peer_id": alice["user_id"]},
    )
    items = resp.json()
    assert len(items) == 2
    for m in items:
        assert m["read_at"] is not None


# ── conversations summary ────────────────────────────────────────────────


async def test_conversations_lists_unread_counts(client, register_user) -> None:
    alice = await register_user(username="alice", password="alicepass1!")
    bob = await register_user(username="bob", password="bobpass123!")
    carol = await register_user(username="carol", password="carolpass1!")

    await _send(client, bob, alice["user_id"], "from bob")
    await _send(client, bob, alice["user_id"], "another from bob")
    await _send(client, carol, alice["user_id"], "from carol")

    resp = await client.get("/api/messages/conversations", headers=alice["headers"])
    assert resp.status_code == 200
    convs = {c["peer_id"]: c for c in resp.json()}
    assert convs[bob["user_id"]]["unread_count"] == 2
    assert convs[carol["user_id"]]["unread_count"] == 1


# ── unseal-batch ─────────────────────────────────────────────────────────


async def test_unseal_batch_limit_enforced(client, two_users) -> None:
    """Batch is hard-capped at 200; sending 201 must be rejected."""
    alice, bob = two_users
    sealed = await _seal(client, alice, bob["user_id"], "x")
    item = {
        "sender_id": alice["user_id"],
        "recipient_id": bob["user_id"],
        "encrypted_payload_hex": sealed["encrypted_payload_hex"],
        "nonce_hex": sealed["nonce_hex"],
        "signature_hex": sealed["signature_hex"],
    }
    resp = await client.post(
        "/api/crypto/unseal-batch",
        headers=bob["headers"],
        json={"items": [item] * 201},
    )
    assert resp.status_code == 400
