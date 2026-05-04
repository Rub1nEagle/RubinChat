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

// --app-height: высота лейаута, привязанная к РЕАЛЬНОЙ видимой области.
// Используем window.innerHeight, потому что он сжимается при показе/скрытии
// адресной строки (и Safari, и Chrome), но НЕ реагирует на экранную
// клавиатуру (та меняет visualViewport.height, а не innerHeight).
// Так лейаут перестаёт уезжать за интерфейс браузера, а сам интерфейс
// не «улетает» при наборе текста.
function setAppHeight() {
    document.documentElement.style.setProperty(
        "--app-height",
        `${window.innerHeight}px`,
    );
}
setAppHeight();
window.addEventListener("resize", setAppHeight);
window.addEventListener("orientationchange", setAppHeight);
// Скрытие/показ адресной строки в Safari/Chrome иногда не дёргает resize,
// но всегда меняет visualViewport. Подписка на visualViewport.resize
// не вредит — innerHeight всё равно остаётся стабильным при клавиатуре.
if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", setAppHeight);
}

const app = new App({
    target: document.getElementById("app"),
});

export default app;
