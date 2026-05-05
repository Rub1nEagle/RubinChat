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
