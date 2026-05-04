import { writable, derived } from "svelte/store";

// Маленький helper: writable, синхронизированный с localStorage.
function persisted(key, initial) {
    let raw = null;
    try {
        raw = localStorage.getItem(key);
    } catch (_) {
        raw = null;
    }
    let start = initial;
    if (raw !== null) {
        try {
            start = JSON.parse(raw);
        } catch (_) {
            start = initial;
        }
    }
    const store = writable(start);
    store.subscribe((value) => {
        try {
            if (value === null || value === undefined) localStorage.removeItem(key);
            else localStorage.setItem(key, JSON.stringify(value));
        } catch (_) {
            /* ignore quota / disabled storage */
        }
    });
    return store;
}

// Сессия пользователя — хранится между перезагрузками.
// { token, user_id, username, private_key_hex }
export const session = persisted("rubinchat.session", null);

export const isAuthenticated = derived(session, ($s) => !!$s?.token);

// Тема оформления: "dark" | "light". Применяется к <html> через app-skeleton.
export const theme = persisted("rubinchat.theme", "dark");

export function toggleTheme() {
    theme.update((t) => (t === "dark" ? "light" : "dark"));
}

// Транзиентные данные текущего сеанса в памяти.
export const contacts = writable([]);          // [{user_id, username, public_key_hex}]
export const activePeerId = writable(null);    // number | null
export const messages = writable([]);          // [MessageOut + plaintext + signatureValid]
export const wsState = writable("offline");    // "online" | "offline" | "connecting"

// Сводки переписок: peer_id -> {
//   last_message: MessageOut | null,
//   last_preview: string,         // расшифрованный текст для sidebar
//   unread_count: number,
// }
export const conversations = writable({});

// Эфемерное состояние «печатает» / «отгружает картинку», приходит по WS.
// peer_id -> { kind: "text"|"image", expiresAt: ms }
export const typingByPeer = writable({});

export function logout() {
    session.set(null);
    contacts.set([]);
    activePeerId.set(null);
    messages.set([]);
    conversations.set({});
    typingByPeer.set({});
    wsState.set("offline");
}
