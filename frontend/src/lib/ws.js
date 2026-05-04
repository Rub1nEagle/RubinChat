// Маленький WebSocket-клиент с автопереподключением и публикацией статуса
// в стор. Снаружи слушаем события через addListener(callback).
import { get } from "svelte/store";
import { session, wsState } from "./stores.js";

let socket = null;
let listeners = new Set();
let reconnectTimer = null;
let manualClose = false;

function url() {
    const { token } = get(session) || {};
    if (!token) return null;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/ws?token=${encodeURIComponent(token)}`;
}

export function connect() {
    if (socket && socket.readyState <= 1) return;
    const target = url();
    if (!target) return;

    manualClose = false;
    wsState.set("connecting");
    socket = new WebSocket(target);

    socket.addEventListener("open", () => wsState.set("online"));
    socket.addEventListener("close", () => {
        wsState.set("offline");
        socket = null;
        if (manualClose) return;
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connect, 2000);
    });
    socket.addEventListener("message", (event) => {
        let data;
        try {
            data = JSON.parse(event.data);
        } catch {
            return;
        }
        for (const fn of listeners) fn(data);
    });
}

export function disconnect() {
    manualClose = true;
    clearTimeout(reconnectTimer);
    if (socket) {
        socket.close();
        socket = null;
    }
    wsState.set("offline");
}

export function addListener(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
}

export function send(payload) {
    if (!socket || socket.readyState !== 1) return false;
    socket.send(JSON.stringify(payload));
    return true;
}
