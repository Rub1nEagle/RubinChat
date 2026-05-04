<script>
    import { onDestroy } from "svelte";
    import { initials, colorFor } from "../lib/format.js";
    import { users as usersApi } from "../lib/api.js";

    export let name = "";
    export let size = 40;
    export let online = false;
    export let showOnlineDot = false;
    /** Если задано — компонент попробует подгрузить аватар по /users/{id}/avatar.
     *  Падение или 404 → молча показываем инициалы. */
    export let userId = null;
    export let hasAvatar = false;
    /** Меняется при обновлении аватара — триггер для перезагрузки. */
    export let avatarVersion = 0;

    let url = "";
    let lastKey = "";

    // Кеш blob-URL'ов на уровне модуля: один и тот же аватар не качаем
    // десять раз для десяти Avatar-компонентов (контактлист + хедер + ...).
    if (!globalThis.__rubinchat_avatar_cache) {
        globalThis.__rubinchat_avatar_cache = new Map();
    }
    const cache = globalThis.__rubinchat_avatar_cache;

    async function loadAvatar() {
        const key = `${userId}:${avatarVersion}`;
        if (key === lastKey) return;
        lastKey = key;
        if (!userId || !hasAvatar) {
            url = "";
            return;
        }
        if (cache.has(key)) {
            url = cache.get(key);
            return;
        }
        try {
            const blob = await usersApi.fetchAvatarBlob(userId);
            if (!blob) { url = ""; return; }
            const objectUrl = URL.createObjectURL(blob);
            cache.set(key, objectUrl);
            // Удалим устаревшие версии этого пользователя.
            for (const k of cache.keys()) {
                if (k !== key && k.startsWith(`${userId}:`)) {
                    URL.revokeObjectURL(cache.get(k));
                    cache.delete(k);
                }
            }
            url = objectUrl;
        } catch (_) {
            url = "";
        }
    }

    $: void userId, hasAvatar, avatarVersion, loadAvatar();
</script>

<div class="relative shrink-0" style="width: {size}px; height: {size}px;">
    {#if url}
        <img src={url} alt={name}
             class="rounded-full w-full h-full object-cover select-none" />
    {:else}
        <div class="rounded-full bg-gradient-to-br {colorFor(name)} grid place-items-center
                    text-white font-semibold select-none w-full h-full"
             style="font-size: {Math.round(size * 0.4)}px;">
            {initials(name)}
        </div>
    {/if}
    {#if showOnlineDot && online}
        <span class="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-tg-success
                     ring-2 ring-tg-bg"></span>
    {/if}
</div>
