<script>
    import { createEventDispatcher, tick } from "svelte";
    import { fade, fly } from "svelte/transition";
    import { portal } from "../lib/portal.js";
    import { compressImage } from "../lib/image.js";

    export let disabled = false;
    /** Если задан — композер в режиме редактирования. */
    export let editing = null; // { id, plaintext } | null
    /** Pending-вложение, его жизненным циклом управляет родитель.
     *  { name, size, kind, previewUrl?, status: "compressing" | "uploading" | "ready" | "error", error? } | null */
    export let attachment = null;

    let text = "";
    let textarea;
    let imageInput;
    let fileInput;

    // Меню «скрепка»: { x, y } в координатах вьюпорта; null = закрыто.
    let attachMenu = null;
    let attachButton;

    const dispatch = createEventDispatcher();

    const IMAGE_ALLOWED = new Set(["image/jpeg", "image/png", "image/webp", "image/gif"]);
    const IMAGE_MAX_BYTES = 20 * 1024 * 1024; // до сжатия — щедро. После сжатия сервер всё равно ловит на 5 МБ.
    const FILE_MAX_BYTES = 5 * 1024 * 1024;   // ровно как лимит сервера, чтобы не гонять впустую.

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

    function openAttachMenu() {
        if (disabled || editing) return;
        if (!attachButton) return;
        const r = attachButton.getBoundingClientRect();
        const MENU_W = 180;
        const MENU_H = 96; // ≈ две строки меню; уточнится после монтирования
        // Рисуем меню НАД скрепкой: на мобиле снизу всё закрывает клавиатура
        // когда композер в фокусе, а тут фокус ещё на textarea.
        attachMenu = {
            x: Math.max(8, r.left),
            y: Math.max(8, r.top - MENU_H - 4),
        };
    }

    function closeAttachMenu() {
        attachMenu = null;
    }

    function pickPhoto() {
        closeAttachMenu();
        imageInput?.click();
    }

    function pickAnyFile() {
        closeAttachMenu();
        fileInput?.click();
    }

    async function onImage(e) {
        const f = e.target.files?.[0];
        if (!f) return;
        e.target.value = "";
        if (!IMAGE_ALLOWED.has(f.type)) {
            dispatch("error", "Поддерживаются jpeg / png / webp / gif");
            return;
        }
        if (f.size > IMAGE_MAX_BYTES) {
            dispatch("error", `Картинка больше ${(IMAGE_MAX_BYTES / 1024 / 1024).toFixed(0)} МБ`);
            return;
        }
        // Сжимаем в браузере, чтобы не нагружать сервер.
        const compressed = await compressImage(f);
        dispatch("pickFile", { file: compressed, kind: "image" });
    }

    async function onFile(e) {
        const f = e.target.files?.[0];
        if (!f) return;
        e.target.value = "";
        if (f.size > FILE_MAX_BYTES) {
            dispatch("error", `Файл больше ${(FILE_MAX_BYTES / 1024 / 1024).toFixed(0)} МБ`);
            return;
        }
        dispatch("pickFile", { file: f, kind: "file" });
    }

    function formatBytes(n) {
        if (!Number.isFinite(n)) return "";
        if (n < 1024) return `${n} Б`;
        if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} КБ`;
        return `${(n / 1024 / 1024).toFixed(1)} МБ`;
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
                <!-- Файл без превью: иконка-документ. -->
                <div class="w-12 h-12 rounded-lg bg-tg-accent/10 text-tg-accent
                            grid place-items-center shrink-0">
                    <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                         stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <path d="M14 2v6h6"/>
                    </svg>
                </div>
            {/if}
            <div class="min-w-0 flex-1">
                <div class="text-sm truncate">{attachment.name || (attachment.kind === "file" ? "файл" : "image")}</div>
                <div class="text-xs text-tg-muted truncate">
                    {attachment.size ? `${formatBytes(attachment.size)} · ` : ""}{statusLabel}
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
                   bind:this={imageInput} on:change={onImage} class="hidden" />
            <input type="file" bind:this={fileInput} on:change={onFile} class="hidden" />
            <button type="button"
                    bind:this={attachButton}
                    on:click={openAttachMenu}
                    disabled={disabled}
                    class="w-10 h-10 sm:w-12 sm:h-12 rounded-full
                           text-tg-muted hover:text-tg-text hover:bg-tg-text/5
                           grid place-items-center shrink-0
                           disabled:opacity-40 disabled:cursor-not-allowed
                           transition-colors duration-150"
                    title="Прикрепить">
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

{#if attachMenu}
    <!-- Через portal, чтобы position:fixed не ломался от transform/filter
         у предков (Composer внутри bg-tg-panel + grid Chat). -->
    <div use:portal>
        <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
        <div class="fixed inset-0 z-40"
             on:click={closeAttachMenu}
             on:contextmenu|preventDefault={closeAttachMenu}
             transition:fade={{ duration: 100 }}>
        </div>
        <div class="fixed z-50 min-w-[180px]
                    bg-tg-panel text-tg-text border border-tg-divider rounded-xl shadow-xl py-1"
             style="left: {attachMenu.x}px; top: {attachMenu.y}px;"
             in:fly={{ y: 4, duration: 140 }}>
            <button class="w-full text-left px-3 py-2 text-sm hover:bg-tg-text/5 flex items-center gap-2"
                    on:click={pickPhoto}>
                <svg class="w-4 h-4 text-tg-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <path d="M21 15l-5-5L5 21"/>
                </svg>
                Фото
            </button>
            <button class="w-full text-left px-3 py-2 text-sm hover:bg-tg-text/5 flex items-center gap-2"
                    on:click={pickAnyFile}>
                <svg class="w-4 h-4 text-tg-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <path d="M14 2v6h6"/>
                </svg>
                Файлы
            </button>
        </div>
    </div>
{/if}
