// Минимальный SPA-роутер: history.pushState + writable store
// с текущим pathname. FastAPI отдаёт index.html на любом пути,
// клиент сам решает, что показать.
import { writable } from "svelte/store";

export const path = writable(window.location.pathname);

window.addEventListener("popstate", () => path.set(window.location.pathname));

export function navigate(to, replace = false) {
    if (to === window.location.pathname) return;
    if (replace) history.replaceState({}, "", to);
    else history.pushState({}, "", to);
    path.set(to);
}
