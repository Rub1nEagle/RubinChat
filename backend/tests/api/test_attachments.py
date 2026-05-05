"""Attachment upload + download tests (image + generic file paths).

Both kinds go through the same `/api/messages/upload` route; they differ in:
* allowed mime list (image — strict whitelist, file — blacklist),
* whether `original_filename` is stored,
* response `Content-Disposition` (inline vs attachment).
"""
from __future__ import annotations


# ── helpers ──────────────────────────────────────────────────────────────


async def _upload_image(client, sender, recipient_id, *, content=b"\xff\xd8\xffjpegbody"):
    files = {"file": ("photo.jpg", content, "image/jpeg")}
    data = {
        "recipient_id": str(recipient_id),
        "sender_private_key_hex": sender["private_key_hex"],
        "kind": "image",
    }
    return await client.post(
        "/api/messages/upload",
        headers=sender["headers"],
        data=data,
        files=files,
    )


async def _upload_file(client, sender, recipient_id, *, filename="report.pdf",
                       mime="application/pdf", content=b"%PDF-1.7\n%fake"):
    files = {"file": (filename, content, mime)}
    data = {
        "recipient_id": str(recipient_id),
        "sender_private_key_hex": sender["private_key_hex"],
        "kind": "file",
    }
    return await client.post(
        "/api/messages/upload",
        headers=sender["headers"],
        data=data,
        files=files,
    )


# ── image path (regression: existing flow still works) ───────────────────


async def test_upload_image_keeps_no_original_filename(client, two_users) -> None:
    alice, bob = two_users
    resp = await _upload_image(client, alice, bob["user_id"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["mime_type"] == "image/jpeg"
    assert body["size_bytes"] > 0
    assert body["original_filename"] is None


async def test_upload_image_rejects_disallowed_mime(client, two_users) -> None:
    alice, bob = two_users
    files = {"file": ("evil.svg", b"<svg/>", "image/svg+xml")}
    data = {
        "recipient_id": str(bob["user_id"]),
        "sender_private_key_hex": alice["private_key_hex"],
        "kind": "image",
    }
    resp = await client.post(
        "/api/messages/upload",
        headers=alice["headers"],
        data=data,
        files=files,
    )
    assert resp.status_code == 400


# ── file path (new) ──────────────────────────────────────────────────────


async def test_upload_file_stores_original_filename(client, two_users) -> None:
    alice, bob = two_users
    resp = await _upload_file(
        client, alice, bob["user_id"],
        filename="quarterly-report.pdf",
        mime="application/pdf",
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["mime_type"] == "application/pdf"
    assert body["original_filename"] == "quarterly-report.pdf"


async def test_upload_file_rejects_dangerous_mime(client, two_users) -> None:
    """HTML files would let one user host XSS on our origin via the
    decrypted blob URL — the service blacklists them.
    """
    alice, bob = two_users
    resp = await _upload_file(
        client, alice, bob["user_id"],
        filename="evil.html",
        mime="text/html",
        content=b"<script>alert(1)</script>",
    )
    assert resp.status_code == 400


async def test_upload_file_too_large_rejected(client, two_users) -> None:
    alice, bob = two_users
    big = b"\x00" * (5 * 1024 * 1024 + 2048)  # past MAX_BYTES + the route's 1KB slack
    resp = await _upload_file(
        client, alice, bob["user_id"],
        filename="huge.bin",
        mime="application/octet-stream",
        content=big,
    )
    assert resp.status_code == 413


async def test_upload_file_unknown_kind_rejected(client, two_users) -> None:
    alice, bob = two_users
    files = {"file": ("foo.bin", b"x", "application/octet-stream")}
    data = {
        "recipient_id": str(bob["user_id"]),
        "sender_private_key_hex": alice["private_key_hex"],
        "kind": "video",  # not supported
    }
    resp = await client.post(
        "/api/messages/upload",
        headers=alice["headers"],
        data=data,
        files=files,
    )
    assert resp.status_code == 400


# ── download with proper Content-Disposition ────────────────────────────


async def test_download_image_is_inline(client, two_users) -> None:
    alice, bob = two_users
    upload = await _upload_image(client, alice, bob["user_id"])
    att_id = upload.json()["id"]

    resp = await client.get(
        f"/api/messages/attachment/{att_id}",
        headers=bob["headers"],
    )
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "inline" in cd
    assert resp.headers.get("x-signature-valid") == "1"
    # nosniff обязателен — иначе старые браузеры могут MIME-sniff'ить
    # HTML внутри blob'а в обход Content-Disposition.
    assert resp.headers.get("x-content-type-options") == "nosniff"


async def test_upload_accepts_missing_content_type(client, two_users) -> None:
    """curl без -H Content-Type или редкое расширение не должны падать в
    400 — роут подставляет дефолтный application/octet-stream.
    """
    alice, bob = two_users
    files = {"file": ("notes.dat", b"opaque blob", None)}
    data = {
        "recipient_id": str(bob["user_id"]),
        "sender_private_key_hex": alice["private_key_hex"],
        "kind": "file",
    }
    resp = await client.post(
        "/api/messages/upload",
        headers=alice["headers"],
        data=data,
        files=files,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["mime_type"] == "application/octet-stream"


async def test_download_file_is_attachment_with_filename(client, two_users) -> None:
    alice, bob = two_users
    content = b"PK\x03\x04 the content does not really matter"
    upload = await _upload_file(
        client, alice, bob["user_id"],
        filename="секретные данные.zip",
        mime="application/zip",
        content=content,
    )
    att_id = upload.json()["id"]

    resp = await client.get(
        f"/api/messages/attachment/{att_id}",
        headers=bob["headers"],
    )
    assert resp.status_code == 200
    assert resp.content == content
    cd = resp.headers.get("content-disposition", "")
    assert cd.startswith("attachment;")
    # RFC 5987 form must be present so cyrillic name survives the trip.
    assert "filename*=UTF-8''" in cd
    assert "%D1%81%D0%B5%D0%BA%D1%80%D0%B5%D1%82" in cd  # начало "секрет" в percent-encoded UTF-8


# ── full message-with-attachment flow ───────────────────────────────────


async def _seal_text(client, sender, recipient_id, plaintext):
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


async def test_full_flow_send_message_with_file(client, two_users) -> None:
    """Upload → POST /messages with attachment_id → list → fetch blob.

    Catches breakage in the attachment_id ↔ Message wiring that
    individual upload/download tests miss.
    """
    alice, bob = two_users
    file_bytes = b"PK\x03\x04 fake zip body"

    upload = await _upload_file(
        client, alice, bob["user_id"],
        filename="archive.zip", mime="application/zip", content=file_bytes,
    )
    att_id = upload.json()["id"]

    sealed = await _seal_text(client, alice, bob["user_id"], "вот файл")
    create = await client.post(
        "/api/messages/",
        headers=alice["headers"],
        json={
            "recipient_id": bob["user_id"],
            "encrypted_payload_hex": sealed["encrypted_payload_hex"],
            "nonce_hex": sealed["nonce_hex"],
            "signature_hex": sealed["signature_hex"],
            "attachment_id": att_id,
        },
    )
    assert create.status_code == 201, create.text
    msg = create.json()
    assert msg["attachment"]["id"] == att_id
    assert msg["attachment"]["original_filename"] == "archive.zip"

    # Recipient sees it in the list, with attachment metadata intact.
    listed = await client.get(
        "/api/messages/",
        headers=bob["headers"],
        params={"peer_id": alice["user_id"]},
    )
    items = listed.json()
    assert len(items) == 1
    att = items[0]["attachment"]
    assert att["id"] == att_id
    assert att["mime_type"] == "application/zip"

    # And the recipient can actually download the bytes.
    blob = await client.get(
        f"/api/messages/attachment/{att_id}",
        headers=bob["headers"],
    )
    assert blob.status_code == 200
    assert blob.content == file_bytes


async def test_attachment_must_belong_to_conversation(client, register_user) -> None:
    """Alice uploads a file aimed at Bob, then tries to attach it to a
    message to Carol — the service must reject (sender_id/recipient_id
    on the attachment lock it to the original pair).
    """
    alice = await register_user(username="alice", password="alicepass1!")
    bob = await register_user(username="bob", password="bobpass123!")
    carol = await register_user(username="carol", password="carolpass1!")

    upload = await _upload_file(
        client, alice, bob["user_id"],
        filename="for-bob.txt", mime="text/plain", content=b"private note",
    )
    att_id = upload.json()["id"]

    sealed = await _seal_text(client, alice, carol["user_id"], "hi")
    resp = await client.post(
        "/api/messages/",
        headers=alice["headers"],
        json={
            "recipient_id": carol["user_id"],
            "encrypted_payload_hex": sealed["encrypted_payload_hex"],
            "nonce_hex": sealed["nonce_hex"],
            "signature_hex": sealed["signature_hex"],
            "attachment_id": att_id,
        },
    )
    assert resp.status_code == 400


async def test_download_attachment_only_for_participants(client, register_user) -> None:
    alice = await register_user(username="alice", password="alicepass1!")
    bob = await register_user(username="bob", password="bobpass123!")
    eve = await register_user(username="eve", password="evepass1234!")

    upload = await _upload_file(
        client, alice, bob["user_id"], filename="private.txt",
        mime="text/plain", content=b"shared with bob only",
    )
    att_id = upload.json()["id"]

    # Eve is neither sender nor recipient — must get 404.
    resp = await client.get(
        f"/api/messages/attachment/{att_id}",
        headers=eve["headers"],
    )
    assert resp.status_code == 404
