<script>
    import { createEventDispatcher, tick } from "svelte";
    import { fade, fly } from "svelte/transition";
    import { portal } from "../lib/portal.js";

    export let mine = false;
    export let open = false;
    /** Якорь меню в координатах вьюпорта: {x, y} — верхний-левый угол.
     *  Меню рендерится `position: fixed` и автоматически отзеркаливается,
     *  если не помещается на экране. */
    export let coords = null;

    const dispatch = createEventDispatcher();

    let menuEl;
    let pos = { x: 0, y: 0 };

    // Перепозиционируем меню после монтирования: измеряем настоящий
    // размер и не даём вылезти за границы экрана.
    $: if (open && coords) {
        pos = { ...coords };
        tick().then(() => {
            if (!menuEl) return;
            const r = menuEl.getBoundingClientRect();
            const margin = 8;
            let x = coords.x;
            let y = coords.y;
            if (x + r.width > window.innerWidth - margin) {
                x = window.innerWidth - r.width - margin;
            }
            if (x < margin) x = margin;
            if (y + r.height > window.innerHeight - margin) {
                y = Math.max(margin, coords.y - r.height - 4);
            }
            if (y < margin) y = margin;
            pos = { x, y };
        });
    }

    function pick(action) {
        dispatch("action", action);
        dispatch("close");
    }

    function onOverlayClick() {
        dispatch("close");
    }

    function onOverlayContext(e) {
        // ПКМ вне сообщения — глушим нативное меню браузера и закрываем нашу.
        // Меню открывается ТОЛЬКО на пузыре (там — отдельный contextmenu-handler).
        e.preventDefault();
        dispatch("close");
    }
</script>

{#if open}
    <!-- Через portal монтируем в <body>: иначе при transform у предков
         (group hover, transitions) фиксированное позиционирование сломается. -->
    <div use:portal>
        <!-- Невидимый overlay на весь viewport: ловит любые клики/ПКМ
             вне меню и закрывает его. preventDefault на contextmenu
             отключает нативное меню браузера, чтобы оно не вылазило. -->
        <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
        <div class="fixed inset-0 z-40"
             on:click={onOverlayClick}
             on:contextmenu={onOverlayContext}
             transition:fade={{ duration: 100 }}>
        </div>

        <div bind:this={menuEl}
             class="fixed z-50 min-w-[180px]
                    bg-tg-panel text-tg-text border border-tg-divider rounded-xl shadow-xl py-1"
             style="left: {pos.x}px; top: {pos.y}px;"
             in:fly={{ y: -4, duration: 140 }}>

            <button class="w-full text-left px-3 py-2 text-sm hover:bg-tg-text/5 flex items-center gap-2"
                    on:click={() => pick("info")}>
                <svg class="w-4 h-4 text-tg-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="9"/>
                    <path d="M12 8v4M12 16h.01"/>
                </svg>
                Информация
            </button>

            {#if mine}
                <button class="w-full text-left px-3 py-2 text-sm hover:bg-tg-text/5 flex items-center gap-2"
                        on:click={() => pick("edit")}>
                    <svg class="w-4 h-4 text-tg-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                         stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 20h9"/>
                        <path d="M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
                    </svg>
                    Редактировать
                </button>
                <div class="my-1 border-t border-tg-divider"></div>
                <button class="w-full text-left px-3 py-2 text-sm hover:bg-tg-danger/15 text-tg-danger
                               flex items-center gap-2"
                        on:click={() => pick("delete")}>
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                         stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M3 6h18"/>
                        <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                    </svg>
                    Удалить
                </button>
            {/if}
        </div>
    </div>
{/if}
