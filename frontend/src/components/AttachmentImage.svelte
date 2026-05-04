<script>
    import { onMount, onDestroy } from "svelte";
    import { messages as messagesApi } from "../lib/api.js";
    import ImageViewerModal from "./ImageViewerModal.svelte";

    /** @type {{ id: number, mime_type: string, size_bytes: number }} */
    export let attachment;

    let url = "";
    let signatureValid = true;
    let loading = true;
    let error = "";
    let viewerOpen = false;

    async function load() {
        loading = true;
        error = "";
        try {
            const { blob, signatureValid: ok } = await messagesApi.fetchAttachmentBlob(attachment.id);
            url = URL.createObjectURL(blob);
            signatureValid = ok;
        } catch (e) {
            error = e.message || "не удалось загрузить";
        } finally {
            loading = false;
        }
    }

    onMount(load);
    onDestroy(() => {
        if (url) URL.revokeObjectURL(url);
    });

    function openFull() {
        if (url) viewerOpen = true;
    }
</script>

<div class="my-1">
    {#if loading}
        <div class="rounded-xl bg-tg-bg/40 border border-tg-divider
                    w-[220px] h-[160px] grid place-items-center text-tg-muted text-xs">
            Расшифровка картинки…
        </div>
    {:else if error}
        <div class="rounded-xl bg-tg-danger/10 border border-tg-danger/30
                    px-3 py-2 text-xs text-tg-danger">
            Не удалось загрузить картинку: {error}
        </div>
    {:else}
        <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-noninteractive-element-interactions -->
        <img src={url}
             alt="Вложение"
             loading="lazy"
             decoding="async"
             on:click={openFull}
             class="rounded-xl max-w-full max-h-[360px] object-contain
                    cursor-zoom-in select-none" />
        {#if !signatureValid}
            <div class="text-[11px] text-tg-danger mt-1">⚠ подпись картинки не прошла проверку</div>
        {/if}
    {/if}
</div>

{#if viewerOpen}
    <ImageViewerModal {url} on:close={() => (viewerOpen = false)} />
{/if}
