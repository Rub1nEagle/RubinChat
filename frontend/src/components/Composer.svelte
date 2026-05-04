<script>
    import { createEventDispatcher, tick } from "svelte";
    import { fly } from "svelte/transition";
    import { compressImage } from "../lib/image.js";

    export let disabled = false;
    /** Если задан — композер в режиме редактирования. */
    export let editing = null; // { id, plaintext } | null
    /** Pending-вложение, его жизненным циклом управляет родитель.
     *  { name, size, previewUrl, status: "compressing" | "uploading" | "ready" | "error", error? } | null */
    export let attachment = null;

    let text = "";
    let textarea;
    let fileInput;

    const dispatch = createEventDispatcher();

    const ALLOWED = new Set(["image/jpeg", "image/png", "image/webp", "image/gif"]);
    const MAX_BYTES = 20 * 1024 * 1024; // до сжатия — щедро. После сжатия сервер всё равно ловит на 5 МБ.

    async function autosize() {
        await tick();
        if (!textarea) return;
        textarea.style.height = "0";
        textarea.style.height = Math.min(textarea.scrollHeight, 160) + "px";
    }

    let lastEditingId = null;
    $: if (editing && editing.id !== lastEditingId) {
        lastEditingId = editing.id;
        text = editing.plaintext ?? "";
        dispatch("clearAttachment");
        tick().then(() => {
            autosize();
            textarea?.focus();
        });
    } else if (!editing && lastEditingId !== null) {
        lastEditingId = null;
        text = "";
        autosize();
    }

    function pickFile() {
        if (disabled || editing) return;
        fileInput?.click();
    }

    async function onFile(e) {
        const f = e.target.files?.[0];
        if (!f) return;
        e.target.value = "";
        if (!ALLOWED.has(f.type)) {
            dispatch("error", "Поддерживаются jpeg / png / webp / gif");
            return;
        }
        if (f.size > MAX_BYTES) {
            dispatch("error", `Файл больше ${(MAX_BYTES / 1024 / 1024).toFixed(0)} МБ`);
            return;
        }
        // Сжимаем в браузере, чтобы не нагружать сервер.
        const compressed = await compressImage(f);
        dispatch("pickFile", { file: compressed });
    }

    function removeAttachment() {
        dispatch("clearAttachment");
    }

    function submit() {
        if (disabled) return;
        const value = text.trim();
        if (editing) {
            if (!value) return;
            dispatch("editSubmit", { id: editing.id, text: value });
            text = "";
            autosize();
            return;
        }
        if (!value && !attachment) return;
        // Send даём всегда; если вложение ещё шифруется — ждать будет родитель.
        dispatch("send", { text: value });
        text = "";
        autosize();
        // На мобилках при потере фокуса клавиатура схлопывается — поэтому
        // после отправки явно возвращаем фокус в textarea, чтобы
        // пользователь мог сразу продолжить набор.
        textarea?.focus({ preventScroll: true });
    }

    function cancel() {
        text = "";
        dispatch("clearAttachment");
        dispatch("cancelEdit");
        autosize();
    }

    function onKey(e) {
        if (e.key === "Escape" && editing) {
            e.preventDefault();
            cancel();
            return;
        }
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
        }
    }

    // Композер шлёт сигнал «печатаю» каждый раз, когда пользователь вводит
    // символ. Родитель сам разрулит дросселирование и WS-отправку.
    function onInput() {
        autosize();
        if (!editing && text.length > 0) dispatch("typing");
    }

    $: statusLabel = (() => {
        if (!attachment) return "";
        if (attachment.status === "compressing") return "сжатие…";
        if (attachment.status === "uploading")
            return `загрузка ${attachment.progress ?? 0}%`;
        if (attachment.status === "error") return `ошибка: ${attachment.error || "не загрузилось"}`;
        return "готово ✓";
    })();
</script>

<div class="border-t border-tg-divider bg-tg-panel/70 backdrop-blur px-2 sm:px-3 py-2 sm:py-3"
     style="padding-bottom: max(0.5rem, env(safe-area-inset-bottom));">
    {#if editing}
        <div class="max-w-4xl mx-auto mb-2 px-3 py-2 rounded-xl
                    bg-tg-accent/10 border border-tg-accent/30
                    flex items-center gap-3 text-sm"
             in:fly={{ y: 6, duration: 160 }}>
            <svg class="w-4 h-4 text-tg-accent shrink-0" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 20h9"/>
                <path d="M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
            </svg>
            <div class="flex-1 min-w-0">
                <div class="text-xs uppercase tracking-wider text-tg-accent">Редактирование</div>
                <div class="text-tg-muted truncate">{editing.plaintext}</div>
            </div>
            <button type="button" class="text-tg-muted hover:text-tg-text p-1 rounded-full"
                    on:click={cancel} title="Отмена (Esc)">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 6L6 18"/><path d="M6 6l12 12"/>
                </svg>
            </button>
        </div>
    {/if}

    {#if attachment && !editing}
        <div class="max-w-4xl mx-auto mb-2 flex items-center gap-3
                    bg-tg-bg/60 border border-tg-divider rounded-xl px-2 py-2"
             in:fly={{ y: 6, duration: 160 }}>
            {#if attachment.previewUrl}
                <img src={attachment.previewUrl} alt="превью"
                     class="w-12 h-12 rounded-lg object-cover shrink-0" />
            {:else}
                <div class="w-12 h-12 rounded-lg bg-tg-text/5 shrink-0"></div>
            {/if}
            <div class="min-w-0 flex-1">
                <div class="text-sm truncate">{attachment.name || "image"}</div>
                <div class="text-xs text-tg-muted truncate">
                    {attachment.size ? `${(attachment.size / 1024).toFixed(0)} КБ · ` : ""}{statusLabel}
                </div>
                {#if attachment.status === "uploading" || attachment.status === "compressing"}
                    <div class="h-1 mt-1 rounded-full bg-tg-text/10 overflow-hidden">
                        <div class="h-full bg-tg-accent transition-[width] duration-150"
                             style="width: {attachment.progress ?? 0}%"></div>
                    </div>
                {/if}
            </div>
            <button type="button"
                    class="text-tg-muted hover:text-tg-text p-1 rounded-full hover:bg-tg-text/5"
                    on:click={removeAttachment}
                    title="Убрать">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 6L6 18"/><path d="M6 6l12 12"/>
                </svg>
            </button>
        </div>
    {/if}

    <div class="flex items-end gap-1.5 sm:gap-2 max-w-4xl mx-auto">
        {#if !editing}
            <input type="file" accept="image/jpeg,image/png,image/webp,image/gif"
                   bind:this={fileInput} on:change={onFile} class="hidden" />
            <button type="button"
                    on:click={pickFile}
                    disabled={disabled}
                    class="w-10 h-10 sm:w-12 sm:h-12 rounded-full
                           text-tg-muted hover:text-tg-text hover:bg-tg-text/5
                           grid place-items-center shrink-0
                           disabled:opacity-40 disabled:cursor-not-allowed
                           transition-colors duration-150"
                    title="Прикрепить картинку">
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m21.44 11.05-9.19 9.19a6 6 0 1 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66L9.41 17.42a2 2 0 0 1-2.83-2.83l8.49-8.49"/>
                </svg>
            </button>
        {/if}
        <div class="flex-1 bg-tg-bg/80 border border-tg-divider rounded-2xl
                    px-2.5 sm:px-3 py-1 sm:py-2
                    focus-within:border-tg-accent focus-within:shadow-glow
                    transition-all duration-150">
            <textarea
                bind:this={textarea}
                bind:value={text}
                on:input={onInput}
                on:keydown={onKey}
                placeholder={editing ? "Изменить сообщение"
                    : attachment ? "Подпись к картинке (необязательно)"
                    : "Сообщение"}
                rows="1"
                maxlength="8000"
                {disabled}
                class="w-full bg-transparent text-tg-text placeholder:text-tg-muted
                       outline-none resize-none leading-snug py-1.5 text-[15px] sm:text-base
                       disabled:opacity-60"
            ></textarea>
        </div>
        <button
            type="button"
            on:click={submit}
            disabled={disabled || (!text.trim() && !attachment)}
            class="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-tg-accent text-white
                   grid place-items-center shrink-0
                   hover:bg-tg-accentHover active:scale-90
                   disabled:opacity-40 disabled:cursor-not-allowed
                   transition-all duration-150 shadow-ruby"
            title={editing ? "Сохранить" : "Отправить"}
        >
            {#if editing}
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M4 12l5 5L20 6"/>
                </svg>
            {:else}
                <svg viewBox="0 0 24 24" class="w-5 h-5" fill="currentColor">
                    <path d="M3.4 20.6L21.5 12 3.4 3.4 3.4 10.2 16 12 3.4 13.8z"/>
                </svg>
            {/if}
        </button>
    </div>
</div>
