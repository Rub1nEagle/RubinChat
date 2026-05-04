<script>
    import { fly } from "svelte/transition";

    /** Список «в полёте»: каждый элемент — отдельное сообщение,
     *  у которого ещё не закончилась загрузка / шифрование / доставка.
     *  { id, name, previewUrl, progress (0..100), status: "uploading" | "sealing" | "sending" | "error", error? } */
    export let items = [];

    let expanded = false;

    function statusLabel(it) {
        if (it.status === "error") return `ошибка${it.error ? `: ${it.error}` : ""}`;
        if (it.status === "uploading") return `Фото отправляется… ${it.progress ?? 0}%`;
        if (it.status === "sealing") return "шифрование на сервере…";
        if (it.status === "sending") return "отправка…";
        return "";
    }

    function lineColor(it) {
        return it.status === "error" ? "bg-tg-danger" : "bg-tg-accent";
    }
</script>

{#if items.length > 0}
    <div class="max-w-4xl mx-auto mb-2 bg-tg-bg/60 border border-tg-divider rounded-xl
                overflow-hidden"
         in:fly={{ y: 6, duration: 160 }}>
        {#if items.length === 1}
            {@const it = items[0]}
            <div class="flex items-center gap-3 px-2 py-2">
                {#if it.previewUrl}
                    <img src={it.previewUrl} alt=""
                         class="w-10 h-10 rounded-lg object-cover shrink-0" />
                {:else}
                    <div class="w-10 h-10 rounded-lg bg-tg-text/5 shrink-0"></div>
                {/if}
                <div class="min-w-0 flex-1">
                    <div class="text-sm truncate">{it.name || "Картинка"}</div>
                    <div class="text-xs text-tg-muted truncate">{statusLabel(it)}</div>
                    <div class="h-1 mt-1 rounded-full bg-tg-text/10 overflow-hidden">
                        <div class="h-full transition-[width] duration-150 {lineColor(it)}"
                             style="width: {it.status === 'uploading' ? (it.progress ?? 0) : 100}%"></div>
                    </div>
                </div>
            </div>
        {:else}
            <button class="w-full flex items-center gap-3 px-3 py-2 text-left
                           hover:bg-tg-text/5 transition-colors"
                    on:click={() => (expanded = !expanded)}>
                <div class="w-10 h-10 rounded-lg bg-tg-accent/15 text-tg-accent
                            grid place-items-center shrink-0">
                    <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                         stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <circle cx="8.5" cy="8.5" r="1.5"/>
                        <path d="M21 15l-5-5L5 21"/>
                    </svg>
                </div>
                <div class="min-w-0 flex-1">
                    <div class="text-sm font-medium">
                        Отправляется {items.length} {items.length === 1 ? "фото" : items.length < 5 ? "фото" : "фото"}
                    </div>
                    <div class="text-xs text-tg-muted">
                        {items.filter((x) => x.status === "uploading").length > 0
                            ? `${Math.min(...items.map((x) => x.progress ?? 0))}% — ${Math.max(...items.map((x) => x.progress ?? 0))}%`
                            : "шифрование и подпись…"}
                    </div>
                </div>
                <svg class="w-4 h-4 text-tg-muted transition-transform"
                     style="transform: rotate({expanded ? 180 : 0}deg)"
                     viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M6 9l6 6 6-6"/>
                </svg>
            </button>

            {#if expanded}
                <ul class="border-t border-tg-divider divide-y divide-tg-divider
                           max-h-[40vh] overflow-y-auto">
                    {#each items as it (it.id)}
                        <li class="flex items-center gap-3 px-2 py-2">
                            {#if it.previewUrl}
                                <img src={it.previewUrl} alt=""
                                     class="w-10 h-10 rounded-lg object-cover shrink-0" />
                            {:else}
                                <div class="w-10 h-10 rounded-lg bg-tg-text/5 shrink-0"></div>
                            {/if}
                            <div class="min-w-0 flex-1">
                                <div class="text-sm truncate">{it.name || "Картинка"}</div>
                                <div class="text-xs text-tg-muted truncate">{statusLabel(it)}</div>
                                <div class="h-1 mt-1 rounded-full bg-tg-text/10 overflow-hidden">
                                    <div class="h-full transition-[width] duration-150 {lineColor(it)}"
                                         style="width: {it.status === 'uploading' ? (it.progress ?? 0) : 100}%"></div>
                                </div>
                            </div>
                        </li>
                    {/each}
                </ul>
            {/if}
        {/if}
    </div>
{/if}
