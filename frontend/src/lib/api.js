// Обёртка вокруг fetch + автоматический Bearer-токен из стора сессии.
// При получении 401 — выкидываем сессию и перенаправляем на /.
import { get } from "svelte/store";
import { logout, session } from "./stores.js";
import { navigate } from "./router.js";

async function request(method, path, body) {
    const $session = get(session);
    const headers = { "Content-Type": "application/json" };
    if ($session?.token) headers.Authorization = `Bearer ${$session.token}`;

    const res = await fetch(path, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401) {
        logout();
        navigate("/");
        throw new Error("сессия истекла");
    }

    if (res.status === 204) return null;

    let data = null;
    try {
        data = await res.json();
    } catch (_) {
        data = null;
    }

    if (!res.ok) {
        const detail = data?.detail || `${res.status} ${res.statusText}`;
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
}

export const api = {
    get: (path) => request("GET", path),
    post: (path, body) => request("POST", path, body),
    patch: (path, body) => request("PATCH", path, body),
    del: (path) => request("DELETE", path),
};

// Высокоуровневые вызовы.
export const auth = {
    login: ({ username, password }) =>
        api.post("/api/auth/login", { username, password }),
    register: ({ username, password }) =>
        api.post("/api/auth/register", { username, password }),
    changePassword: ({ currentPassword, newPassword }) =>
        api.post("/api/auth/change-password", {
            current_password: currentPassword,
            new_password: newPassword,
        }),
    deleteAccount: ({ password }) =>
        api.post("/api/auth/delete-account", { password }),
};

async function authedFetch(path, opts = {}) {
    const $session = get(session);
    const headers = { ...(opts.headers || {}) };
    if ($session?.token) headers.Authorization = `Bearer ${$session.token}`;
    const res = await fetch(path, { ...opts, headers });
    if (res.status === 401) {
        logout();
        navigate("/");
        throw new Error("сессия истекла");
    }
    return res;
}

export const users = {
    list: () => api.get("/api/users/"),
    me: () => api.get("/api/users/me"),
    profile: (userId) => api.get(`/api/users/${userId}`),
    publicKey: (userId) => api.get(`/api/users/${userId}/public-key`),
    updateMe: (payload) => api.patch("/api/users/me", payload),
    uploadAvatar: async (file) => {
        const fd = new FormData();
        fd.append("file", file, file.name || "avatar");
        const res = await authedFetch("/api/users/me/avatar", { method: "POST", body: fd });
        let data = null;
        try { data = await res.json(); } catch (_) {}
        if (!res.ok) throw new Error(data?.detail || `${res.status} ${res.statusText}`);
        return data;
    },
    removeAvatar: async () => {
        const res = await authedFetch("/api/users/me/avatar", { method: "DELETE" });
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.json();
    },
    fetchAvatarBlob: async (userId) => {
        const res = await authedFetch(`/api/users/${userId}/avatar`);
        if (res.status === 404) return null;
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.blob();
    },
};

export const messages = {
    list: ({ peerId, limit = 200, beforeId } = {}) => {
        const qp = new URLSearchParams();
        if (peerId !== undefined && peerId !== null) qp.set("peer_id", String(peerId));
        if (limit) qp.set("limit", String(limit));
        if (beforeId !== undefined && beforeId !== null) qp.set("before_id", String(beforeId));
        const suffix = qp.toString() ? `?${qp.toString()}` : "";
        return api.get(`/api/messages/${suffix}`);
    },
    send: (payload) => api.post("/api/messages/", payload),
    edit: (id, payload) => api.patch(`/api/messages/${id}`, payload),
    remove: (id) => api.del(`/api/messages/${id}`),
    markRead: (peerId) => api.post(`/api/messages/read?peer_id=${peerId}`),
    conversations: () => api.get("/api/messages/conversations"),
    /** Загрузить вложение: server-side seal/sign по схеме проекта.
     *  Через XHR, чтобы знать прогресс HTTP-upload (для UI «N%»).
     *  `kind`: "image" — картинка (сжимается на клиенте, узкий whitelist
     *  на сервере), "file" — произвольный файл (имя сохраняется).
     *  Возвращает { id, mime_type, size_bytes, original_filename }. */
    upload: ({ file, recipientId, senderPrivateKeyHex, kind = "image", onProgress }) =>
        new Promise((resolve, reject) => {
            const $session = get(session);
            const fd = new FormData();
            fd.append("recipient_id", String(recipientId));
            fd.append("sender_private_key_hex", senderPrivateKeyHex);
            fd.append("kind", kind);
            // file.name важен для kind=file: сервер сохранит его в
            // original_filename и проставит в Content-Disposition при отдаче.
            fd.append("file", file, file.name || (kind === "file" ? "file" : "image"));
            const xhr = new XMLHttpRequest();
            xhr.open("POST", "/api/messages/upload");
            if ($session?.token) {
                xhr.setRequestHeader("Authorization", `Bearer ${$session.token}`);
            }
            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable && typeof onProgress === "function") {
                    onProgress(Math.min(100, Math.round((e.loaded / e.total) * 100)));
                }
            };
            xhr.onerror = () => reject(new Error("сетевая ошибка"));
            xhr.onabort = () => reject(new Error("загрузка отменена"));
            xhr.onload = () => {
                if (xhr.status === 401) {
                    logout();
                    navigate("/");
                    reject(new Error("сессия истекла"));
                    return;
                }
                let data = null;
                try { data = JSON.parse(xhr.responseText); } catch (_) {}
                if (xhr.status >= 200 && xhr.status < 300) resolve(data);
                else {
                    const detail = data?.detail || `${xhr.status} ${xhr.statusText}`;
                    reject(new Error(typeof detail === "string" ? detail : JSON.stringify(detail)));
                }
            };
            xhr.send(fd);
        }),
    /** Скачать расшифрованный blob картинки (с авторизацией). */
    fetchAttachmentBlob: async (attachmentId) => {
        const $session = get(session);
        const headers = {};
        if ($session?.token) headers.Authorization = `Bearer ${$session.token}`;
        const res = await fetch(`/api/messages/attachment/${attachmentId}`, { headers });
        if (res.status === 401) {
            logout();
            navigate("/");
            throw new Error("сессия истекла");
        }
        if (!res.ok) {
            throw new Error(`${res.status} ${res.statusText}`);
        }
        const blob = await res.blob();
        const signatureValid = res.headers.get("X-Signature-Valid") !== "0";
        return { blob, signatureValid };
    },
};

export const crypto = {
    seal: ({ recipientId, plaintext, senderPrivateKeyHex }) =>
        api.post("/api/crypto/seal", {
            recipient_id: recipientId,
            plaintext,
            sender_private_key_hex: senderPrivateKeyHex,
        }),
    unseal: ({ senderId, recipientId, encryptedPayloadHex, nonceHex, signatureHex }) =>
        api.post("/api/crypto/unseal", {
            sender_id: senderId,
            recipient_id: recipientId,
            encrypted_payload_hex: encryptedPayloadHex,
            nonce_hex: nonceHex,
            signature_hex: signatureHex,
        }),
    unsealBatch: (items) =>
        api.post("/api/crypto/unseal-batch", {
            items: items.map((m) => ({
                sender_id: m.sender_id,
                recipient_id: m.recipient_id,
                encrypted_payload_hex: m.encrypted_payload_hex,
                nonce_hex: m.nonce_hex,
                signature_hex: m.signature_hex,
            })),
        }),
    fingerprint: (peerId) => api.get(`/api/crypto/fingerprint/${peerId}`),
};
