import "./app.css";
import App from "./App.svelte";

// Применить сохранённую тему до монтирования компонентов, чтобы
// не было «вспышки» белого фона на тёмной теме.
try {
    const raw = localStorage.getItem("rubinchat.theme");
    const stored = raw ? JSON.parse(raw) : "dark";
    document.documentElement.classList.toggle("dark", stored !== "light");
} catch (_) {
    document.documentElement.classList.add("dark");
}

// --app-height: высота лейаута, привязанная к ВИДИМОЙ области.
// Используем visualViewport.height: он сжимается и при показе/скрытии
// адресной строки, и при появлении экранной клавиатуры. Так чат
// сжимается ровно на высоту клавиатуры — Composer остаётся над ней,
// и iOS не форс-скроллит документ, чтобы поднять фокус в видимую зону
// (именно эта автопрокрутка раньше создавала пустое пространство внизу).
// Fallback на innerHeight — для совсем старых браузеров.
function setAppHeight() {
    const h = window.visualViewport?.height ?? window.innerHeight;
    document.documentElement.style.setProperty("--app-height", `${h}px`);
}
setAppHeight();
window.addEventListener("orientationchange", setAppHeight);
if (window.visualViewport) {
    // visualViewport.resize стреляет и при клавиатуре, и при адресной
    // строке — одного источника достаточно.
    window.visualViewport.addEventListener("resize", setAppHeight);
    // Когда iOS поднимает визуальный viewport относительно layout-вьюпорта
    // (автопрокрутка к фокусу), height мог не пересчитаться — слушаем scroll.
    window.visualViewport.addEventListener("scroll", setAppHeight);
} else {
    window.addEventListener("resize", setAppHeight);
}

const app = new App({
    target: document.getElementById("app"),
});

export default app;
