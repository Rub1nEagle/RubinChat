<script>
    import { afterUpdate, tick, createEventDispatcher } from "svelte";
    import { fly } from "svelte/transition";
    import { flip } from "svelte/animate";
    import MessageBubble from "./MessageBubble.svelte";
    import { formatDay, sameDay } from "../lib/format.js";

    export let messages = [];
    export let myUserId;
    /** Флаг от родителя: «сейчас идёт догрузка старых». Прячем UI-триггер, пока не закончится. */
    export let loadingOlder = false;
    /** Если ``false`` — больше старых сообщений нет, не зовём ``loadOlder`` повторно. */
    export let hasMoreOlder = true;

    const dispatch = createEventDispatcher();

    const NEAR_TOP_PX = 200;

    let container;
    let pinnedToBottom = true;
    let prevLen = 0;
    /** При prepend старых сообщений нужно «дотянуть» scrollTop, иначе картинка
     *  скакнёт вверх (визуально вьюпорт окажется на новых старых). Перед
     *  prepend родитель вызывает ``beforePrepend()``; после рендера afterUpdate
     *  компенсирует разницу высот. */
    let pendingPrependFromHeight = null;

    /** Вызывается родителем непосредственно перед `messages.update(...prepend...)`. */
    export function beforePrepend() {
        if (container) pendingPrependFromHeight = container.scrollHeight;
    }

    function maybeRequestOlder() {
        if (!container) return;
        if (loadingOlder || !hasMoreOlder) return;
        if (messages.length === 0) return;
        if (container.scrollTop <= NEAR_TOP_PX) {
            dispatch("loadOlder");
        }
    }

    function onScroll() {
        if (!container) return;
        const slack = 60;
        pinnedToBottom =
            container.scrollHeight - container.scrollTop - container.clientHeight < slack;
        maybeRequestOlder();
    }

    afterUpdate(async () => {
        await tick();
        if (!container) return;

        // Компенсация после prepend'а: ставим scrollTop так, чтобы визуально
        // пользователь оставался на тех же сообщениях, что и до догрузки.
        if (pendingPrependFromHeight !== null) {
            const delta = container.scrollHeight - pendingPrependFromHeight;
            container.scrollTop += delta;
            pendingPrependFromHeight = null;
            prevLen = messages.length;
            // После compensation проверим, не открыли ли тут же шанс на ещё один батч
            // (например, на больших экранах prepend дал > NEAR_TOP_PX, но не намного).
            maybeRequestOlder();
            return;
        }

        const len = messages.length;
        const isFirstFill = prevLen === 0 && len > 0;
        if (isFirstFill) {
            container.scrollTop = container.scrollHeight;
            pinnedToBottom = true;
        } else if (pinnedToBottom) {
            container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
        }
        prevLen = len;
    });

    // Группируем сообщения по дням, чтобы вставлять разделители.
    $: groups = (() => {
        const out = [];
        let lastDate = null;
        for (const m of messages) {
            const d = new Date(m.created_at);
            if (!lastDate || !sameDay(d, lastDate)) {
                out.push({ kind: "day", id: `day-${m.id}`, iso: m.created_at });
                lastDate = d;
            }
            out.push({ kind: "msg", id: `m-${m.id}`, message: m });
        }
        return out;
    })();
</script>

<div bind:this={container} on:scroll={onScroll}
     class="flex-1 min-h-0 overflow-y-auto overscroll-contain px-4 py-4 tg-pattern">
    {#if loadingOlder}
        <div class="flex justify-center py-2 text-xs text-tg-muted">
            <span class="inline-flex items-center gap-1.5">
                <span class="typing-dot"></span>
                <span class="typing-dot" style="animation-delay: 0.15s"></span>
                <span class="typing-dot" style="animation-delay: 0.30s"></span>
                Загружаем более ранние сообщения…
            </span>
        </div>
    {:else if !hasMoreOlder && messages.length > 0}
        <div class="flex justify-center py-2 text-[11px] text-tg-muted/70">
            Это начало переписки
        </div>
    {/if}
    <div class="flex flex-col gap-1.5 max-w-4xl mx-auto">
        {#each groups as item (item.id)}
            <div animate:flip={{ duration: 250 }}>
                {#if item.kind === "day"}
                    <div class="flex justify-center my-2"
                         in:fly={{ y: 4, duration: 200 }}>
                        <span class="px-3 py-1 rounded-full bg-black/30 text-tg-muted text-xs">
                            {formatDay(item.iso)}
                        </span>
                    </div>
                {:else}
                    <div in:fly={{ y: 8, duration: 220 }}>
                        <MessageBubble
                            message={item.message}
                            mine={item.message.sender_id === myUserId}
                            on:info={(e) => dispatch("info", e.detail)}
                            on:edit={(e) => dispatch("edit", e.detail)}
                            on:delete={(e) => dispatch("delete", e.detail)} />
                    </div>
                {/if}
            </div>
        {:else}
            <div class="text-center text-tg-muted text-sm mt-12">
                Здесь пока пусто. Скажите «привет» 👋
            </div>
        {/each}
    </div>
</div>
