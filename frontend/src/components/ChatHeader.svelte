<script>
    import { createEventDispatcher } from "svelte";
    import Avatar from "./Avatar.svelte";
    import { wsState, typingByPeer } from "../lib/stores.js";
    import { displayName, lastSeen } from "../lib/format.js";

    /** @type {{ user_id: number, username: string, display_name: string|null, is_online?: boolean, last_seen_at?: string|null } | null} */
    export let peer;

    const dispatch = createEventDispatcher();

    function openProfile() {
        if (peer) dispatch("open-profile", peer.user_id);
    }
    function back() {
        dispatch("back");
    }

    // Активен ли индикатор «печатает» именно у текущего собеседника.
    $: typing = peer ? $typingByPeer[peer.user_id] : null;
    $: typingActive = typing && typing.expiresAt > Date.now();
    $: typingLabel = typingActive
        ? (typing.kind === "image" ? "загружает картинку" : "печатает")
        : "";
</script>

<header class="h-14 sm:h-16 px-2 sm:px-5 flex items-center gap-1.5 sm:gap-3
               border-b border-tg-divider bg-tg-panel/70 backdrop-blur">
    {#if peer}
        <!-- На мобилке — кнопка «назад» к списку -->
        <button class="md:hidden text-tg-muted hover:text-tg-text p-1.5 -ml-1 rounded-full
                       hover:bg-tg-text/5 transition shrink-0"
                title="Назад к списку"
                on:click={back}>
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M19 12H5"/>
                <path d="M12 19l-7-7 7-7"/>
            </svg>
        </button>

        <button class="flex items-center gap-2 sm:gap-3 min-w-0 flex-1
                       -mx-1 sm:-mx-2 px-1 sm:px-2 py-1 rounded-lg
                       hover:bg-tg-text/5 transition-colors text-left"
                on:click={openProfile}>
            <span class="hidden sm:block">
                <Avatar name={displayName(peer)} size={40}
                        userId={peer.user_id}
                        hasAvatar={peer.has_avatar}
                        avatarVersion={peer.avatar_version || 0}
                        online={peer.is_online} showOnlineDot />
            </span>
            <span class="sm:hidden">
                <Avatar name={displayName(peer)} size={34}
                        userId={peer.user_id}
                        hasAvatar={peer.has_avatar}
                        avatarVersion={peer.avatar_version || 0}
                        online={peer.is_online} showOnlineDot />
            </span>
            <div class="min-w-0 flex-1">
                <div class="font-semibold truncate text-[15px] sm:text-base leading-tight">
                    {displayName(peer)}
                </div>
                <div class="text-[11px] sm:text-xs truncate leading-tight
                            {typingActive ? 'text-tg-accent' : 'text-tg-muted'}">
                    {#if typingActive}
                        <span class="inline-flex items-center gap-1 align-middle">
                            <span class="typing-dot"></span>
                            <span class="typing-dot" style="animation-delay: 0.15s;"></span>
                            <span class="typing-dot" style="animation-delay: 0.30s;"></span>
                        </span>
                        {typingLabel}…
                    {:else if $wsState !== "online"}
                        {$wsState === "connecting" ? "подключение…" : "нет связи с сервером"}
                    {:else if peer.is_online}
                        <span class="inline-block w-1.5 h-1.5 rounded-full bg-tg-success mr-1 align-middle"></span>
                        в сети
                    {:else}
                        {lastSeen(peer.last_seen_at, false)}
                    {/if}
                </div>
            </div>
        </button>
        <!-- На мобилке шапка целиком кликабельна — иконку «info» прячем,
             чтобы освободить место. -->
        <button class="hidden sm:inline-flex items-center justify-center
                       text-tg-muted hover:text-tg-text p-2 rounded-full
                       hover:bg-tg-text/5 transition"
                title="Сведения о собеседнике"
                on:click={openProfile}>
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 8v4M12 16h.01" />
            </svg>
        </button>
    {:else}
        <div class="text-tg-muted text-sm">Выберите чат, чтобы начать переписку</div>
    {/if}
</header>
