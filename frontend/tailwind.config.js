/** @type {import('tailwindcss').Config} */
export default {
    darkMode: "class",
    content: ["./index.html", "./src/**/*.{svelte,js}"],
    theme: {
        extend: {
            // Все цвета бренда — из CSS-переменных. Их значения переключает
            // класс `.dark` на <html>, см. app.css.
            colors: {
                tg: {
                    bg:          "rgb(var(--tg-bg) / <alpha-value>)",
                    sidebar:     "rgb(var(--tg-sidebar) / <alpha-value>)",
                    panel:       "rgb(var(--tg-panel) / <alpha-value>)",
                    surface:     "rgb(var(--tg-surface) / <alpha-value>)",
                    surfaceHi:   "rgb(var(--tg-surface-hi) / <alpha-value>)",
                    incoming:    "rgb(var(--tg-incoming) / <alpha-value>)",
                    divider:     "rgb(var(--tg-divider) / <alpha-value>)",
                    accent:      "rgb(var(--tg-accent) / <alpha-value>)",
                    accentHover: "rgb(var(--tg-accent-hover) / <alpha-value>)",
                    accentDeep:  "rgb(var(--tg-accent-deep) / <alpha-value>)",
                    muted:       "rgb(var(--tg-muted) / <alpha-value>)",
                    text:        "rgb(var(--tg-text) / <alpha-value>)",
                    success:     "rgb(var(--tg-success) / <alpha-value>)",
                    danger:      "rgb(var(--tg-danger) / <alpha-value>)",
                    unread:      "rgb(var(--tg-unread) / <alpha-value>)",
                },
            },
            fontFamily: {
                sans: [
                    "ui-sans-serif",
                    "-apple-system",
                    "BlinkMacSystemFont",
                    "Segoe UI",
                    "Roboto",
                    "Helvetica Neue",
                    "Arial",
                    "sans-serif",
                ],
            },
            boxShadow: {
                bubble: "0 1px 1px rgba(0,0,0,0.18)",
                glow: "0 0 0 3px rgb(var(--tg-accent) / 0.25)",
                ruby: "0 8px 24px -8px rgb(var(--tg-accent) / 0.45)",
            },
            keyframes: {
                pop: {
                    "0%": { transform: "scale(0.92)", opacity: "0" },
                    "60%": { transform: "scale(1.02)" },
                    "100%": { transform: "scale(1)", opacity: "1" },
                },
                pulseDot: {
                    "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
                    "40%": { transform: "scale(1)", opacity: "1" },
                },
                shimmer: {
                    "0%": { backgroundPosition: "-200px 0" },
                    "100%": { backgroundPosition: "200px 0" },
                },
                modalIn: {
                    "0%": { opacity: "0", transform: "translateY(8px) scale(0.98)" },
                    "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
                },
            },
            animation: {
                pop: "pop 220ms cubic-bezier(0.2, 0.9, 0.3, 1.2)",
                "pulse-dot": "pulseDot 1.2s infinite ease-in-out",
                shimmer: "shimmer 1.6s infinite linear",
                "modal-in": "modalIn 180ms ease-out",
            },
        },
    },
    plugins: [],
};
