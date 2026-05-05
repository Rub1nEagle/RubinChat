<script>
    import { onMount, onDestroy } from "svelte";
    import { fly } from "svelte/transition";

    import ContactList from "../components/ContactList.svelte";
    import ChatHeader from "../components/ChatHeader.svelte";
    import MessageList from "../components/MessageList.svelte";
    import Composer from "../components/Composer.svelte";
    import Avatar from "../components/Avatar.svelte";
    import MessageInfoModal from "../components/MessageInfoModal.svelte";
    import ProfileModal from "../components/ProfileModal.svelte";
    import ConfirmDialog from "../components/ConfirmDialog.svelte";
    import SendingAttachments from "../components/SendingAttachments.svelte";

    import { users, messages as messagesApi, crypto } from "../lib/api.js";
    import {
        session, contacts, activePeerId, messages, conversations, wsState, logout,
        theme, toggleTheme, typingByPeer,
    } from "../lib/stores.js";
    import * as ws from "../lib/ws.js";
    import { navigate } from "../lib/router.js";

    let loadingContacts = true;
    let loadingMessages = false;
    let toast = "";
    let toastTimer;

    let editing = null;       // { id, plaintext }
    let infoMessage = null;   // open info modal
    let profile = null;       // { userId, editable } | null
    let confirmDelete = null; // message объект, который сейчас просим удалить
    let myProfile = null;     // {has_avatar, avatar_version, ...}

    // Бесконечная подгрузка старых при скролле вверх.
    let loadingOlder = false;
    let hasMoreOlder = true;
    let messageListRef;       // bind:this — для compensation скролла при prepend

    // Pending-вложение для активной переписки. Загрузка стартует сразу
    // на pickFile, чтобы пользователь мог продолжать набирать текст.
    //   { name, size, previewUrl, status, error?, peerId, promise, progress }
    // promise резолвится в attachment_id или reject'ит с ошибкой.
    let pendingAttachment = null;

    // «В полёте» — сообщения, по которым пользователь уже нажал
    // «Отправить», но шифрование/доставка ещё идут.
    //   { id, peerId, name, previewUrl, progress, status, error? }
    // status: "uploading" | "sealing" | "sending" | "error"
    let sendingMessages = [];

    function nextSendingId() {
        return (globalThis.crypto?.randomUUID?.() ||
                `s-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
    }

    function patchSending(id, patch) {
        sendingMessages = sendingMessages.map((s) =>
            s.id === id ? { ...s, ...patch } : s,
        );
    }
    function dropSending(id) {
        sendingMessages = sendingMessages.filter((s) => s.id !== id);
    }

    $: activeSendingMessages = sendingMessages.filter(
        (s) => s.peerId === $activePeerId,
    );

    function openPeerProfile(userId) {
        profile = { userId, editable: false };
    }
    function openMyProfile() {
        profile = { userId: $session?.user_id, editable: true };
    }

    $: peer = $contacts.find((c) => c.user_id === $activePeerId) || null;
    $: myUserId = $session?.user_id;

    function showToast(text) {
        toast = text;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => (toast = ""), 3000);
    }

    // ───────────────────────── Crypto helpers ─────────────────────────

    async function decryptOne(m) {
        try {
            const r = await crypto.unseal({
                senderId: m.sender_id,
                recipientId: m.recipient_id,
                encryptedPayloadHex: m.encrypted_payload_hex,
                nonceHex: m.nonce_hex,
                signatureHex: m.signature_hex,
            });
            return { ...m, plaintext: r.plaintext, signature_valid: r.signature_valid };
        } catch (e) {
            return { ...m, plaintext: `[ошибка расшифровки: ${e.message}]`, signature_valid: false };
        }
    }

    async function decryptBatch(items) {
        if (items.length === 0) return [];
        try {
            const { results } = await crypto.unsealBatch(items);
            return items.map((m, i) => ({
                ...m,
                plaintext: results[i]?.plaintext ?? "",
                signature_valid: !!results[i]?.signature_valid,
            }));
        } catch (e) {
            // Если batch упал — возвращаем «битые» сообщения с описанием ошибки.
            return items.map((m) => ({
                ...m,
                plaintext: `[ошибка расшифровки: ${e.message}]`,
                signature_valid: false,
            }));
        }
    }

    async function sealText(plaintext, recipientId) {
        return crypto.seal({
            recipientId,
            plaintext,
            senderPrivateKeyHex: $session.private_key_hex,
        });
    }

    // ───────────────────────── Loading ─────────────────────────

    async function loadContacts() {
        loadingContacts = true;
        try {
            const list = await users.list();
            contacts.set(list);
        } catch (e) {
            showToast(`Не удалось загрузить контакты: ${e.message}`);
        } finally {
            loadingContacts = false;
        }
    }

    function previewFor(message, decryptedText) {
        const txt = (decryptedText || "").trim();
        if (txt) return txt;
        const att = message?.attachment;
        if (att) {
            if (att.mime_type?.startsWith("image/")) return "🖼 Картинка";
            return `📎 ${att.original_filename || "Файл"}`;
        }
        return "";
    }

    async function loadConversations() {
        try {
            const list = await messagesApi.conversations();
            const nextMap = {};
            for (const conv of list) {
                let preview = "";
                if (conv.last_message) {
                    const dec = await decryptOne(conv.last_message);
                    preview = previewFor(conv.last_message, dec.plaintext);
                }
                nextMap[conv.peer_id] = {
                    last_message: conv.last_message,
                    last_preview: preview,
                    unread_count: conv.unread_count,
                };
            }
            conversations.set(nextMap);
        } catch (e) {
            console.warn("conversations:", e);
        }
    }

    // Сколько сообщений расшифровываем сразу одним батчем при открытии
    // переписки — самые свежие. Остальное расшифровывается в фоне.
    const PRIORITY_DECRYPT = 20;
    const BACKGROUND_BATCH = 30;
    const INITIAL_LIMIT = 200;
    const OLDER_BATCH_LIMIT = 100;  // сколько берём за один скролл-ап
    let bgDecryptToken = 0;

    async function loadConversation(peerId) {
        loadingMessages = true;
        messages.set([]);
        loadingOlder = false;
        hasMoreOlder = true;
        // Фоновую задачу прежней беседы остановит инкремент токена.
        const myToken = ++bgDecryptToken;
        try {
            const list = await messagesApi.list({ peerId, limit: INITIAL_LIMIT });
            // Если получили меньше лимита — старее уже нет.
            hasMoreOlder = list.length >= INITIAL_LIMIT;
            // Сразу показываем все сообщения с плейсхолдерами, чтобы лента
            // была видна пользователю целиком.
            const placeholders = list.map((m) => ({
                ...m,
                plaintext: null,
                signature_valid: null,
            }));
            messages.set(placeholders);
            loadingMessages = false;

            // 1. Расшифровываем последние PRIORITY_DECRYPT сообщений одним батчем.
            const total = list.length;
            const priorityCount = Math.min(PRIORITY_DECRYPT, total);
            const priorityRaw = list.slice(total - priorityCount);
            const priorityDec = await decryptBatch(priorityRaw);
            if (myToken !== bgDecryptToken) return; // переключились в другой чат
            applyDecrypted(priorityDec);

            // markRead — после первого видимого экрана.
            try {
                const res = await messagesApi.markRead(peerId);
                if (myToken !== bgDecryptToken) return;
                if (res?.updated > 0) {
                    const now = new Date().toISOString();
                    messages.update((arr) =>
                        arr.map((m) =>
                            m.sender_id === peerId && !m.read_at
                                ? { ...m, read_at: now }
                                : m
                        )
                    );
                    conversations.update((map) => {
                        const conv = map[peerId];
                        if (!conv) return map;
                        return { ...map, [peerId]: { ...conv, unread_count: 0 } };
                    });
                }
            } catch (_) { /* без катастрофы */ }

            // 2. Остальные сообщения — в фоне, батчами по BACKGROUND_BATCH,
            // от свежих к старым, чтобы пользователь видел расшифровку
            // по мере прокрутки вверх.
            const restRaw = list.slice(0, total - priorityCount);
            for (let end = restRaw.length; end > 0; end -= BACKGROUND_BATCH) {
                if (myToken !== bgDecryptToken) return;
                const start = Math.max(0, end - BACKGROUND_BATCH);
                const slice = restRaw.slice(start, end);
                const decrypted = await decryptBatch(slice);
                if (myToken !== bgDecryptToken) return;
                applyDecrypted(decrypted);
            }
        } catch (e) {
            showToast(`Ошибка загрузки переписки: ${e.message}`);
            loadingMessages = false;
        }
    }

    function applyDecrypted(decryptedList) {
        if (!decryptedList || decryptedList.length === 0) return;
        const byId = new Map(decryptedList.map((m) => [m.id, m]));
        messages.update((arr) =>
            arr.map((m) => (byId.has(m.id) ? { ...m, ...byId.get(m.id) } : m))
        );
    }

    /** Догрузка старых сообщений по скроллу вверх. Берёт ``OLDER_BATCH_LIMIT``
     *  сообщений с id < самого верхнего сейчас, prepend'ит плейсхолдеры,
     *  потом расшифровывает батч. Перед prepend'ом просит MessageList
     *  запомнить scrollHeight — иначе вьюпорт скакнёт. */
    async function loadOlder() {
        if (loadingOlder || !hasMoreOlder) return;
        const peerId = $activePeerId;
        if (peerId === null) return;
        const arr = $messages;
        if (arr.length === 0) return;

        const beforeId = arr[0].id;
        const myToken = bgDecryptToken;
        loadingOlder = true;
        try {
            const list = await messagesApi.list({
                peerId,
                limit: OLDER_BATCH_LIMIT,
                beforeId,
            });
            if (myToken !== bgDecryptToken) return;
            if (list.length < OLDER_BATCH_LIMIT) hasMoreOlder = false;
            if (list.length === 0) return;

            // 1. Запомнить scrollHeight ДО prepend'а.
            messageListRef?.beforePrepend?.();

            // 2. Prepend плейсхолдеров.
            messages.update((curr) => [
                ...list.map((m) => ({ ...m, plaintext: null, signature_valid: null })),
                ...curr,
            ]);

            // 3. Расшифровка фоном.
            const decrypted = await decryptBatch(list);
            if (myToken !== bgDecryptToken) return;
            applyDecrypted(decrypted);
        } catch (e) {
            showToast(`Не удалось подгрузить более ранние: ${e.message}`);
        } finally {
            loadingOlder = false;
        }
    }

    // ───────────────────────── Helpers for peer summary ─────────────────────────

    function peerOfMessage(m) {
        return m.sender_id === myUserId ? m.recipient_id : m.sender_id;
    }

    // ───────────────────────── Sending / editing / deleting ─────────────────────────

    function startAttachmentUpload(file, peerId, kind = "image") {
        // Превью локально только для картинок — для файлов оно ни к чему,
        // да и blob: ссылка на условный pdf только сожрёт память.
        const previewUrl = kind === "image" ? URL.createObjectURL(file) : null;
        const att = {
            name: file.name,
            size: file.size,
            kind,
            previewUrl,
            status: "uploading",
            progress: 0,
            peerId,
            promise: null,
        };
        const onProgress = (p) => {
            // Прогресс сначала идёт в pendingAttachment (Composer показывает
            // в превью). После Send этот же объект мигрирует в sendingMessages
            // и патчится по att-ссылке.
            if (pendingAttachment && pendingAttachment._att === att) {
                pendingAttachment = { ...pendingAttachment, progress: p };
            }
            const inFlight = sendingMessages.find((s) => s._att === att);
            if (inFlight) patchSending(inFlight.id, { progress: p });
        };
        att.promise = (async () => {
            try {
                const r = await messagesApi.upload({
                    file,
                    recipientId: peerId,
                    senderPrivateKeyHex: $session.private_key_hex,
                    kind,
                    onProgress,
                });
                // upload закончился — переходим в sealing/ready.
                if (pendingAttachment && pendingAttachment._att === att) {
                    pendingAttachment = {
                        ...pendingAttachment,
                        status: "ready",
                        progress: 100,
                        id: r.id,
                    };
                }
                const inFlight = sendingMessages.find((s) => s._att === att);
                if (inFlight) patchSending(inFlight.id, { progress: 100, status: "sealing" });
                return r.id;
            } catch (e) {
                if (pendingAttachment && pendingAttachment._att === att) {
                    pendingAttachment = { ...pendingAttachment, status: "error", error: e.message };
                }
                const inFlight = sendingMessages.find((s) => s._att === att);
                if (inFlight) patchSending(inFlight.id, { status: "error", error: e.message });
                throw e;
            }
        })();
        pendingAttachment = {
            _att: att,
            name: att.name,
            size: att.size,
            kind,
            previewUrl: att.previewUrl,
            status: "uploading",
            progress: 0,
        };
        // typing-индикатор у нас сейчас умеет text/image; для файлов
        // пусть пока летит тот же image-сигнал (получатель увидит «отправляет вложение»).
        ws.send({ type: "typing", peer_id: peerId, kind: "image" });
    }

    function clearPendingAttachment() {
        if (pendingAttachment?.previewUrl) URL.revokeObjectURL(pendingAttachment.previewUrl);
        pendingAttachment = null;
    }

    async function sendNew({ text }) {
        const peerId = $activePeerId;
        if (peerId === null) return;
        const att = pendingAttachment?._att || null;
        // На время отправки замораживаем pending.
        pendingAttachment = null;
        let inFlightId = null;
        if (att && att.peerId === peerId) {
            inFlightId = nextSendingId();
            // Текущий статус (uploading / ready) определяет точку в баннере.
            const initialStatus = att.status === "ready" ? "sealing" : "uploading";
            sendingMessages = [
                ...sendingMessages,
                {
                    id: inFlightId,
                    peerId,
                    name: att.name,
                    previewUrl: att.previewUrl,
                    progress: att.progress ?? (att.status === "ready" ? 100 : 0),
                    status: initialStatus,
                    _att: att,
                },
            ];
        } else if (att) {
            // Сменили собеседника — старая загрузка к нам уже не относится.
            if (att.previewUrl) URL.revokeObjectURL(att.previewUrl);
        }
        try {
            let attachmentId = null;
            if (inFlightId) {
                attachmentId = await att.promise;
                patchSending(inFlightId, { status: "sending", progress: 100 });
            }
            const plaintext = text && text.trim() ? text : " ";
            const sealed = await sealText(plaintext, peerId);
            const payload = {
                recipient_id: peerId,
                encrypted_payload_hex: sealed.encrypted_payload_hex,
                nonce_hex: sealed.nonce_hex,
                signature_hex: sealed.signature_hex,
                attachment_id: attachmentId,
            };
            const sentViaWs = ws.send({ type: "send", payload });
            if (!sentViaWs) {
                const stored = await messagesApi.send(payload);
                await ingestMessage(stored);
            }
            if (inFlightId) {
                dropSending(inFlightId);
                if (att?.previewUrl) URL.revokeObjectURL(att.previewUrl);
            }
        } catch (e) {
            if (inFlightId) {
                patchSending(inFlightId, { status: "error", error: e.message });
                // Через 4 секунды убираем баннер с ошибкой автоматически.
                setTimeout(() => dropSending(inFlightId), 4000);
            }
            showToast(`Ошибка отправки: ${e.message}`);
        }
    }

    let lastTypingTs = 0;
    function onTyping() {
        const peerId = $activePeerId;
        if (peerId === null) return;
        const now = Date.now();
        // Сообщений «typing» — не чаще раза в 2.5 с, иначе спам по WS.
        if (now - lastTypingTs < 2500) return;
        lastTypingTs = now;
        ws.send({ type: "typing", peer_id: peerId, kind: "text" });
    }

    async function submitEdit({ id, text }) {
        const peerId = $activePeerId;
        if (peerId === null) return;
        try {
            const sealed = await sealText(text, peerId);
            const updated = await messagesApi.edit(id, {
                encrypted_payload_hex: sealed.encrypted_payload_hex,
                nonce_hex: sealed.nonce_hex,
                signature_hex: sealed.signature_hex,
            });
            await ingestMessage(updated, { replace: true });
            editing = null;
        } catch (e) {
            showToast(`Не удалось изменить: ${e.message}`);
        }
    }

    function askDelete(m) {
        confirmDelete = m;
    }

    async function performDelete() {
        const m = confirmDelete;
        confirmDelete = null;
        if (!m) return;
        try {
            await messagesApi.remove(m.id);
            removeMessage(m.id);
        } catch (e) {
            showToast(`Не удалось удалить: ${e.message}`);
        }
    }

    function startEdit(m) {
        editing = { id: m.id, plaintext: m.plaintext ?? "" };
    }

    function cancelEdit() {
        editing = null;
    }

    function showInfo(m) {
        infoMessage = m;
    }

    // ───────────────────────── Local store mutations ─────────────────────────

    async function ingestMessage(rawMessage, { replace = false } = {}) {
        const peerId = $activePeerId;
        const decrypted = await decryptOne(rawMessage);

        // Если относится к текущей беседе — обновим список сообщений.
        const involvesActive =
            peerId !== null &&
            (decrypted.sender_id === peerId || decrypted.recipient_id === peerId) &&
            (decrypted.sender_id === myUserId || decrypted.recipient_id === myUserId);
        if (involvesActive) {
            messages.update((arr) => {
                const idx = arr.findIndex((x) => x.id === decrypted.id);
                if (idx >= 0) {
                    const next = arr.slice();
                    next[idx] = decrypted;
                    return next;
                }
                return [...arr, decrypted];
            });
        }

        // Обновим сводку для собеседника (left rail).
        const peerForSummary = peerOfMessage(decrypted);
        conversations.update((map) => {
            const prev = map[peerForSummary] || {
                last_message: null, last_preview: "", unread_count: 0,
            };
            const isIncoming = decrypted.recipient_id === myUserId;
            const isFromActivePeer = peerForSummary === peerId;

            let unread = prev.unread_count;
            if (!replace) {
                if (isFromActivePeer) {
                    unread = 0;                     // открытая беседа = всё прочитано
                } else if (isIncoming) {
                    unread = prev.unread_count + 1; // новое в неоткрытом чате
                }
            }
            return {
                ...map,
                [peerForSummary]: {
                    last_message: decrypted,
                    last_preview: previewFor(decrypted, decrypted.plaintext),
                    unread_count: unread,
                },
            };
        });

        if (decrypted.recipient_id === myUserId && peerForSummary === peerId) {
            // только что пришло в активную беседу — пометить прочитанным.
            try { await messagesApi.markRead(peerForSummary); } catch (_) {}
        }
    }

    function removeMessage(id) {
        messages.update((arr) => arr.filter((m) => m.id !== id));
        // Сводка может устареть; перезагрузим.
        loadConversations();
    }

    // ───────────────────────── WebSocket ─────────────────────────

    function handleWs(data) {
        if (!data) return;
        switch (data.type) {
            case "delivery":
            case "ack":
                if (data.message) ingestMessage(data.message);
                break;
            case "update":
                if (data.message) ingestMessage(data.message, { replace: true });
                break;
            case "delete":
                if (data.message_id) removeMessage(data.message_id);
                break;
            case "read":
                if (data.peer_id) {
                    const reader = data.peer_id;
                    const now = new Date().toISOString();
                    messages.update((arr) =>
                        arr.map((m) =>
                            m.recipient_id === reader && !m.read_at
                                ? { ...m, read_at: now }
                                : m
                        )
                    );
                }
                break;
            case "typing":
                // peer_id = id того, кто печатает.
                if (typeof data.peer_id === "number") {
                    const kind = data.kind === "image" ? "image" : "text";
                    typingByPeer.update((map) => ({
                        ...map,
                        [data.peer_id]: { kind, expiresAt: Date.now() + 4000 },
                    }));
                }
                break;
            case "presence":
                // Сервер прислал смену статуса в сети у одного из контактов.
                // Обновляем стор `contacts`, чтобы зелёная точка / lastSeen
                // у собеседника поменялись без перезагрузки страницы.
                if (typeof data.user_id === "number") {
                    contacts.update((arr) =>
                        arr.map((c) =>
                            c.user_id === data.user_id
                                ? {
                                      ...c,
                                      is_online: !!data.is_online,
                                      last_seen_at: data.last_seen_at ?? c.last_seen_at,
                                  }
                                : c
                        )
                    );
                }
                break;
            case "error":
                showToast(`WS: ${data.error}`);
                break;
        }
    }

    // Чистильщик протухших typing-индикаторов.
    let typingSweeper = null;
    function startTypingSweeper() {
        if (typingSweeper) return;
        typingSweeper = setInterval(() => {
            typingByPeer.update((map) => {
                const now = Date.now();
                let changed = false;
                const next = {};
                for (const [k, v] of Object.entries(map)) {
                    if (v.expiresAt > now) next[k] = v;
                    else changed = true;
                }
                return changed ? next : map;
            });
        }, 1000);
    }

    function pickPeer(c) {
        editing = null;
        clearPendingAttachment();
        activePeerId.set(c.user_id);
        loadConversation(c.user_id);
    }

    function backToList() {
        editing = null;
        clearPendingAttachment();
        activePeerId.set(null);
        messages.set([]);
        loadingOlder = false;
        hasMoreOlder = true;
    }

    function onLogout() {
        logout();
        navigate("/", true);
    }

    async function loadMyProfile() {
        try {
            myProfile = await users.me();
        } catch (_) {}
    }

    let unbind;
    onMount(async () => {
        await Promise.all([loadContacts(), loadMyProfile()]);
        await loadConversations();
        ws.connect();
        unbind = ws.addListener(handleWs);
        startTypingSweeper();
    });
    onDestroy(() => {
        unbind?.();
        ws.disconnect();
        if (typingSweeper) clearInterval(typingSweeper);
    });
</script>

<div class="overflow-hidden grid grid-cols-1 md:grid-cols-[minmax(280px,340px)_1fr]"
     style="height: var(--app-height);">

    <!-- Sidebar — на мобилке скрыт, когда выбран собеседник -->
    <aside class="bg-tg-sidebar border-r border-tg-divider min-h-0 flex-col
                  {peer ? 'hidden md:flex' : 'flex'}">
        <header class="h-16 px-4 flex items-center justify-between border-b border-tg-divider">
            <button class="flex items-center gap-3 min-w-0 flex-1 -mx-2 px-2 py-1 rounded-lg
                           hover:bg-tg-text/5 transition-colors text-left"
                    title="Открыть профиль"
                    on:click={openMyProfile}>
                <Avatar name={$session?.username} size={36}
                        userId={$session?.user_id}
                        hasAvatar={myProfile?.has_avatar || false}
                        avatarVersion={myProfile?.avatar_version || 0}
                        online showOnlineDot />
                <div class="min-w-0">
                    <div class="font-semibold truncate">{$session?.username}</div>
                    <div class="text-xs text-tg-muted truncate">Открыть профиль</div>
                </div>
            </button>
            <div class="flex items-center gap-1 shrink-0">
                <button
                    class="text-tg-muted hover:text-tg-text p-2 rounded-full hover:bg-tg-text/5 transition"
                    title={$theme === "dark" ? "Светлая тема" : "Тёмная тема"}
                    on:click={toggleTheme}
                >
                    {#if $theme === "dark"}
                        <!-- солнце -->
                        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="4"/>
                            <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
                        </svg>
                    {:else}
                        <!-- луна -->
                        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>
                        </svg>
                    {/if}
                </button>
                <button
                    class="text-tg-muted hover:text-tg-text p-2 rounded-full hover:bg-tg-text/5 transition"
                    title="Выйти"
                    on:click={onLogout}
                >
                    <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                         stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                        <path d="M16 17l5-5-5-5" />
                        <path d="M21 12H9" />
                    </svg>
                </button>
            </div>
        </header>

        {#if loadingContacts}
            <div class="px-4 py-6 text-center text-tg-muted text-sm">Загрузка контактов…</div>
        {:else}
            <ContactList
                contacts={$contacts}
                conversations={$conversations}
                activeId={$activePeerId}
                onSelect={pickPeer} />
        {/if}
    </aside>

    <!-- Conversation — на мобилке скрыт, когда никто не выбран -->
    <section class="flex-col min-w-0 min-h-0 bg-tg-bg
                    {peer ? 'flex' : 'hidden md:flex'}">
        <ChatHeader peer={peer}
                    on:open-profile={(e) => openPeerProfile(e.detail)}
                    on:back={backToList} />

        {#if peer}
            {#if loadingMessages && $messages.length === 0}
                <div class="flex-1 grid place-items-center text-tg-muted text-sm">
                    Расшифровка переписки…
                </div>
            {:else}
                <MessageList
                    bind:this={messageListRef}
                    messages={$messages}
                    myUserId={myUserId}
                    loadingOlder={loadingOlder}
                    hasMoreOlder={hasMoreOlder}
                    on:loadOlder={loadOlder}
                    on:info={(e) => showInfo(e.detail)}
                    on:edit={(e) => startEdit(e.detail)}
                    on:delete={(e) => askDelete(e.detail)} />
            {/if}
            <div class="px-2 sm:px-3">
                <SendingAttachments items={activeSendingMessages} />
            </div>
            <Composer
                editing={editing}
                attachment={pendingAttachment}
                on:pickFile={(e) => startAttachmentUpload(e.detail.file, peer.user_id, e.detail.kind)}
                on:clearAttachment={clearPendingAttachment}
                on:send={(e) => sendNew(e.detail)}
                on:editSubmit={(e) => submitEdit(e.detail)}
                on:cancelEdit={cancelEdit}
                on:typing={onTyping}
                on:error={(e) => showToast(e.detail)} />
        {:else}
            <div class="flex-1 grid place-items-center tg-pattern">
                <div class="text-center text-tg-muted px-6">
                    <div class="text-4xl mb-3">💬</div>
                    <div class="text-base">Выберите собеседника слева</div>
                    <div class="text-xs mt-1">Сообщения шифруются и подписываются на стороне клиента</div>
                </div>
            </div>
        {/if}
    </section>
</div>

{#if infoMessage}
    <MessageInfoModal message={infoMessage} myUserId={myUserId}
                      on:close={() => (infoMessage = null)} />
{/if}

{#if profile}
    {#key profile.userId + ':' + profile.editable}
        <ProfileModal userId={profile.userId} editable={profile.editable}
                      on:close={() => (profile = null)} />
    {/key}
{/if}

<ConfirmDialog
    open={confirmDelete !== null}
    title="Удалить сообщение?"
    message={confirmDelete?.plaintext
        ? `«${confirmDelete.plaintext.length > 80
                ? confirmDelete.plaintext.slice(0, 77) + '…'
                : confirmDelete.plaintext}» — отменить нельзя.`
        : "Сообщение будет удалено без возможности восстановления."}
    confirmText="Удалить"
    variant="danger"
    on:confirm={performDelete}
    on:cancel={() => (confirmDelete = null)} />

{#if toast}
    <div class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50"
         in:fly={{ y: 20, duration: 200 }} out:fly={{ y: 20, duration: 200 }}>
        <div class="bg-tg-panel border border-tg-divider px-4 py-2 rounded-xl shadow-lg text-sm">
            {toast}
        </div>
    </div>
{/if}
