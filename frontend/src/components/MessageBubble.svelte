<script>
    import { createEventDispatcher } from "svelte";
    import { formatTime } from "../lib/format.js";
    import MessageMenu from "./MessageMenu.svelte";
    import AttachmentImage from "./AttachmentImage.svelte";
    import AttachmentFile from "./AttachmentFile.svelte";

    export let message;     // { id, sender_id, recipient_id, plaintext, signature_valid, created_at, edited_at, read_at, ... }
    export let mine = false;

    const dispatch = createEventDispatcher();
    let menuOpen = false;
    let menuCoords = null;
    let triggerEl;

    // Меню под кнопкой-троеточием — открываем «лесенкой» рядом с ней.
    function openFromDots() {
        if (!triggerEl) return;
        const r = triggerEl.getBoundingClientRect();
        const MENU_W = 180;
        // Свои сообщения справа → точки слева → меню расширяем вправо.
        // Чужие — наоборот.
        menuCoords = mine
            ? { x: r.left, y: r.bottom + 4 }
            : { x: Math.max(8, r.right - MENU_W), y: r.bottom + 4 };
        menuOpen = true;
    }

    // Правый клик / long-press на пузырь — меню у курсора.
    function openFromContext(e) {
        e.preventDefault();
        menuCoords = { x: e.clientX, y: e.clientY };
        menuOpen = true;
    }
</script>

<div class="group relative flex {mine ? 'justify-end' : 'justify-start'}">
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
    <div class="relative {mine ? 'tg-bubble-out' : 'tg-bubble-in'}"
         on:contextmenu={openFromContext}>
        <!-- Кнопка-«троеточие». На тач-устройствах видна всегда,
             на десктопе — только при hover/focus. -->
        <button
            bind:this={triggerEl}
            class="absolute -top-2 {mine ? '-left-2' : '-right-2'}
                   w-7 h-7 rounded-full bg-tg-panel border border-tg-divider
                   text-tg-muted hover:text-tg-text hover:bg-tg-panel/90
                   shadow-lg
                   opacity-100 md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100
                   transition-opacity duration-150
                   grid place-items-center"
            on:click|stopPropagation={openFromDots}
            aria-label="Меню сообщения"
        >
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <circle cx="5" cy="12" r="1.6"/>
                <circle cx="12" cy="12" r="1.6"/>
                <circle cx="19" cy="12" r="1.6"/>
            </svg>
        </button>

        <MessageMenu
            mine={mine}
            open={menuOpen}
            coords={menuCoords}
            on:close={() => (menuOpen = false)}
            on:action={(e) => dispatch(e.detail, message)}
        />

        {#if message.attachment}
            {#if message.attachment.mime_type?.startsWith("image/")}
                <AttachmentImage attachment={message.attachment} />
            {:else}
                <AttachmentFile attachment={message.attachment} />
            {/if}
        {/if}

        {#if message.plaintext == null}
            <div class="whitespace-pre-wrap leading-relaxed">
                <span class="italic opacity-60">Расшифровка…</span>
            </div>
        {:else if message.plaintext && message.plaintext.trim()}
            <div class="whitespace-pre-wrap leading-relaxed">
                {message.plaintext}
            </div>
        {/if}

        <!--
            mine: пузырь рубиново-белый — мета и галочки светлые.
            !mine: пузырь подстраивается под тему — берём приглушённый
            токеновый цвет, чтобы было видно и в светлой, и в тёмной.
        -->
        <div class="flex items-center justify-end gap-1 mt-1 text-[11px]
                    {mine ? 'text-white/85' : 'text-tg-muted'}">
            {#if message.signature_valid === false}
                <span class="text-tg-danger" title="Подпись не прошла проверку">⚠ подпись</span>
            {/if}
            {#if message.edited_at}
                <span class="italic" title="Сообщение отредактировано">изменено</span>
            {/if}
            <span>{formatTime(message.created_at)}</span>
            {#if mine}
                {#if message.read_at}
                    <!-- двойная галочка «прочитано» — белая на рубине, заметно -->
                    <svg class="w-4 h-4" viewBox="0 0 22 16" fill="none">
                        <path d="M2 9.5l3 3 7-7" stroke="currentColor"
                              stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M8 9.5l3 3 9-9" stroke="currentColor"
                              stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                {:else}
                    <!-- одинарная галочка «отправлено» — приглушённая -->
                    <svg class="w-3.5 h-3.5 opacity-80" viewBox="0 0 16 16" fill="none">
                        <path d="M2 8.5l3.5 3.5L13 4.5" stroke="currentColor"
                              stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                {/if}
            {/if}
        </div>
    </div>
</div>
