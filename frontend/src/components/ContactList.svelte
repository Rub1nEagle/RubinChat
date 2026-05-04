<script>
    import Avatar from "./Avatar.svelte";
    import { displayName, formatTime } from "../lib/format.js";
    import { typingByPeer } from "../lib/stores.js";

    export let contacts = [];
    export let conversations = {};
    export let activeId = null;
    export let onSelect = (_) => {};

    let query = "";

    $: sorted = [...contacts].sort((a, b) => {
        const ca = conversations[a.user_id];
        const cb = conversations[b.user_id];
        const ta = ca?.last_message?.created_at ?? "";
        const tb = cb?.last_message?.created_at ?? "";
        if (ta && tb) return ta < tb ? 1 : -1;
        if (ta) return -1;
        if (tb) return 1;
        return displayName(a).localeCompare(displayName(b));
    });

    // Без запроса — показываем только тех, с кем уже есть переписка
    // (и текущего активного, чтобы он не пропадал в момент выбора).
    // С запросом — ищем по ВСЕЙ базе пользователей: username и display_name.
    $: filtered = (() => {
        const q = query.trim().toLowerCase();
        if (q) {
            return sorted.filter(
                (c) =>
                    c.username.toLowerCase().includes(q) ||
                    (c.display_name || "").toLowerCase().includes(q),
            );
        }
        return sorted.filter(
            (c) =>
                Boolean(conversations[c.user_id]?.last_message) ||
                c.user_id === activeId,
        );
    })();

    $: searching = query.trim().length > 0;

    function preview(c) {
        const conv = conversations[c.user_id];
        if (!conv?.last_message) return "Нет сообщений";
        const text = conv.last_preview || "(зашифровано)";
        return text.length > 64 ? text.slice(0, 60) + "…" : text;
    }
</script>

<div class="px-3 py-3 border-b border-tg-divider">
    <div class="relative">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-tg-muted">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="7" />
                <path d="m21 21-4.3-4.3" />
            </svg>
        </span>
        <input
            class="tg-input pl-9 pr-9 py-2 text-sm bg-tg-bg/60"
            placeholder="Найти собеседника"
            bind:value={query}
        />
        {#if query}
            <button class="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-full
                           text-tg-muted hover:text-tg-text hover:bg-tg-text/5"
                    title="Очистить"
                    on:click={() => (query = "")}>
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 6L6 18"/><path d="M6 6l12 12"/>
                </svg>
            </button>
        {/if}
    </div>
</div>

<ul class="flex-1 overflow-y-auto">
    {#each filtered as c (c.user_id)}
        {@const conv = conversations[c.user_id]}
        {@const unread = conv?.unread_count ?? 0}
        {@const name = displayName(c)}
        {@const typing = $typingByPeer[c.user_id]}
        {@const typingActive = typing && typing.expiresAt > Date.now()}
        <li>
            <button
                class="w-full text-left px-3 py-2.5 flex items-center gap-3
                       hover:bg-tg-text/5 transition-colors duration-150
                       {activeId === c.user_id ? 'bg-tg-accent/15 hover:bg-tg-accent/20' : ''}"
                on:click={() => onSelect(c)}
            >
                <Avatar name={name}
                        userId={c.user_id}
                        hasAvatar={c.has_avatar}
                        avatarVersion={c.avatar_version || 0}
                        online={c.is_online} showOnlineDot />

                <div class="min-w-0 flex-1">
                    <div class="flex items-baseline justify-between gap-2">
                        <div class="font-medium truncate">{name}</div>
                        {#if conv?.last_message}
                            <div class="text-[11px] text-tg-muted shrink-0">
                                {formatTime(conv.last_message.created_at)}
                            </div>
                        {/if}
                    </div>
                    <div class="flex items-center gap-2 mt-0.5">
                        <div class="text-xs truncate flex-1
                                    {typingActive ? 'text-tg-accent' : 'text-tg-muted'}">
                            {#if typingActive}
                                {typing.kind === "image"
                                    ? "загружает картинку…"
                                    : "печатает…"}
                            {:else}
                                {preview(c)}
                            {/if}
                        </div>
                        {#if unread > 0}
                            <span class="shrink-0 inline-flex items-center justify-center
                                         min-w-[20px] h-5 px-1.5 rounded-full
                                         bg-tg-unread text-white text-[11px] font-semibold
                                         shadow-ruby">
                                {unread > 99 ? "99+" : unread}
                            </span>
                        {/if}
                    </div>
                </div>
            </button>
        </li>
    {:else}
        <li class="text-center text-sm text-tg-muted py-8 px-4 leading-relaxed">
            {#if searching}
                Никого не нашли по запросу «{query}»
            {:else}
                Здесь пока никого нет.<br/>
                Найдите собеседника через поиск выше — диалог создастся
                автоматически после первого сообщения.
            {/if}
        </li>
    {/each}
</ul>
