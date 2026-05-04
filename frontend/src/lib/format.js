// Форматирование времени и дат «по-телеграмному».

const TIME_FMT = new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
});

const DAY_FMT = new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
});

const DAY_FMT_FULL = new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
});

export function formatTime(iso) {
    const d = new Date(iso);
    return TIME_FMT.format(d);
}

export function formatDay(iso) {
    const d = new Date(iso);
    const today = new Date();
    if (sameDay(d, today)) return "Сегодня";
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    if (sameDay(d, yesterday)) return "Вчера";
    if (d.getFullYear() === today.getFullYear()) return DAY_FMT.format(d);
    return DAY_FMT_FULL.format(d);
}

export function sameDay(a, b) {
    return (
        a.getFullYear() === b.getFullYear() &&
        a.getMonth() === b.getMonth() &&
        a.getDate() === b.getDate()
    );
}

export function initials(name) {
    if (!name) return "?";
    const parts = name.trim().split(/[\s_.-]+/).filter(Boolean);
    if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
    return (parts[0][0] + parts[1][0]).toUpperCase();
}

// Имя для отображения: display_name → username → "user #id".
export function displayName(user) {
    if (!user) return "";
    return (user.display_name && user.display_name.trim())
        || user.username
        || `user #${user.user_id ?? user.id ?? "?"}`;
}

// Краткое «был N минут назад» для last_seen_at.
export function lastSeen(iso, online = false) {
    if (online) return "в сети";
    if (!iso) return "был давно";
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return "только что был онлайн";
    if (diff < 3600) {
        const m = Math.floor(diff / 60);
        return `был ${m} ${plural(m, ["минуту", "минуты", "минут"])} назад`;
    }
    if (diff < 86400) {
        const h = Math.floor(diff / 3600);
        return `был ${h} ${plural(h, ["час", "часа", "часов"])} назад`;
    }
    if (diff < 86400 * 7) {
        const d = Math.floor(diff / 86400);
        return `был ${d} ${plural(d, ["день", "дня", "дней"])} назад`;
    }
    const f = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" });
    return `был ${f.format(new Date(iso))}`;
}

function plural(n, [one, few, many]) {
    const n10 = n % 10;
    const n100 = n % 100;
    if (n10 === 1 && n100 !== 11) return one;
    if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return few;
    return many;
}

// Группировка hex-строки по 4 символа: "0123 4567 89ab cdef"
export function groupHex(hex, groups = 8, groupLen = 4) {
    if (!hex) return "";
    const slice = hex.slice(0, groups * groupLen);
    return slice.match(new RegExp(`.{1,${groupLen}}`, "g")).join(" ");
}

// Стабильная пастель из имени — для аватарок без картинок.
export function colorFor(name) {
    let h = 0;
    for (let i = 0; i < (name || "").length; i++) {
        h = (h * 31 + name.charCodeAt(i)) >>> 0;
    }
    const palette = [
        "from-rose-500 to-pink-600",
        "from-amber-500 to-orange-600",
        "from-emerald-500 to-teal-600",
        "from-sky-500 to-indigo-600",
        "from-fuchsia-500 to-purple-600",
        "from-lime-500 to-green-600",
        "from-cyan-500 to-blue-600",
    ];
    return palette[h % palette.length];
}
