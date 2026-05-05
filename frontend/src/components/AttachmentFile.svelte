<script>
    import { messages as messagesApi } from "../lib/api.js";

    /** @type {{ id: number, mime_type: string, size_bytes: number, original_filename: string|null }} */
    export let attachment;

    let downloading = false;
    let error = "";

    function formatBytes(n) {
        if (!Number.isFinite(n)) return "";
        if (n < 1024) return `${n} Б`;
        if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} КБ`;
        return `${(n / 1024 / 1024).toFixed(1)} МБ`;
    }

    async function download() {
        if (downloading) return;
        downloading = true;
        error = "";
        try {
            const { blob } = await messagesApi.fetchAttachmentBlob(attachment.id);
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = attachment.original_filename || `attachment-${attachment.id}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            // revoke в следующий тик — чтобы Safari успел начать загрузку.
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (e) {
            error = e.message || "не удалось скачать";
        } finally {
            downloading = false;
        }
    }

    $: name = attachment.original_filename || `файл-${attachment.id}`;
</script>

<button type="button"
        on:click={download}
        disabled={downloading}
        class="my-1 flex items-center gap-3 px-2 py-2 rounded-xl
               bg-tg-bg/40 border border-tg-divider
               hover:bg-tg-bg/70 transition-colors duration-150
               text-left max-w-full disabled:opacity-60 disabled:cursor-wait">
    <div class="w-11 h-11 rounded-lg bg-tg-accent/15 text-tg-accent
                grid place-items-center shrink-0">
        {#if downloading}
            <svg class="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12a9 9 0 1 1-6.2-8.55"/>
            </svg>
        {:else}
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <path d="M14 2v6h6"/>
                <path d="M12 18v-6"/>
                <path d="M9 15l3 3 3-3"/>
            </svg>
        {/if}
    </div>
    <div class="min-w-0 flex-1">
        <div class="text-sm font-medium truncate">{name}</div>
        <div class="text-xs text-tg-muted truncate">
            {formatBytes(attachment.size_bytes)}{#if error} · <span class="text-tg-danger">{error}</span>{/if}
        </div>
    </div>
</button>
