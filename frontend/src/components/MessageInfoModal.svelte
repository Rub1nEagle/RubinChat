<script>
    import { createEventDispatcher } from "svelte";
    import { fade, fly, slide } from "svelte/transition";

    export let message;
    export let myUserId;

    const dispatch = createEventDispatcher();

    let securityOpen = false;

    function close() {
        dispatch("close");
    }

    function copy(text) {
        try {
            navigator.clipboard.writeText(text);
        } catch (_) {
            // ignore — может не быть прав, не критично
        }
    }

    $: createdLocal = new Date(message.created_at).toLocaleString("ru-RU");
    $: editedLocal = message.edited_at
        ? new Date(message.edited_at).toLocaleString("ru-RU")
        : null;
    $: readLocal = message.read_at
        ? new Date(message.read_at).toLocaleString("ru-RU")
        : null;
    $: direction = message.sender_id === myUserId ? "Исходящее" : "Входящее";
    $: signatureLabel =
        message.signature_valid === false ? "не валидна" :
        message.signature_valid === true ? "проверена" : "—";
    $: signatureClass =
        message.signature_valid === false ? "text-tg-danger" :
        message.signature_valid === true ? "text-tg-success" : "text-tg-muted";
</script>

<div class="fixed inset-0 z-50 grid place-items-end sm:place-items-center px-0 sm:px-4 py-0 sm:py-6"
     in:fade={{ duration: 150 }} out:fade={{ duration: 120 }}>
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
    <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" on:click={close}></div>

    <div class="relative w-full max-w-2xl tg-card animate-modal-in
                rounded-b-none sm:rounded-2xl
                max-h-[92vh] sm:max-h-[88vh] overflow-y-auto"
         in:fly={{ y: 12, duration: 180 }}>
        <header class="flex items-center justify-between px-5 py-4 border-b border-tg-divider">
            <div>
                <div class="font-semibold text-lg">Информация о сообщении</div>
                <div class="text-xs text-tg-muted mt-0.5">#{message.id} · {direction}</div>
            </div>
            <button class="text-tg-muted hover:text-tg-text p-2 rounded-full hover:bg-tg-text/5"
                    on:click={close} title="Закрыть">
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 6L6 18"/><path d="M6 6l12 12"/>
                </svg>
            </button>
        </header>

        <div class="px-5 py-4 space-y-4">
            <!-- Открытый текст (как видит клиент) -->
            <section>
                <div class="text-xs uppercase tracking-wider text-tg-muted mb-1.5">
                    Открытый текст
                </div>
                <div class="bg-tg-bg/60 border border-tg-divider rounded-xl px-3 py-2 text-sm
                            whitespace-pre-wrap break-words">
                    {message.plaintext ?? "(не расшифровано)"}
                </div>
            </section>

            <!-- Метаданные -->
            <section class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <div>
                    <div class="text-xs uppercase tracking-wider text-tg-muted">Отправлено</div>
                    <div>{createdLocal}</div>
                </div>
                {#if editedLocal}
                    <div>
                        <div class="text-xs uppercase tracking-wider text-tg-muted">Отредактировано</div>
                        <div>{editedLocal}</div>
                    </div>
                {/if}
                {#if readLocal}
                    <div>
                        <div class="text-xs uppercase tracking-wider text-tg-muted">Прочитано</div>
                        <div>{readLocal}</div>
                    </div>
                {/if}
            </section>

            <!-- Безопасность — свёрнутая по умолчанию -->
            <section class="border border-tg-divider rounded-xl overflow-hidden">
                <button type="button"
                        class="w-full flex items-center gap-2 px-3 py-2.5 text-left
                               hover:bg-tg-text/5 transition-colors"
                        on:click={() => (securityOpen = !securityOpen)}>
                    <span class="inline-flex items-center justify-center w-7 h-7 rounded-lg
                                 bg-tg-accent/15 text-tg-accent shrink-0">
                        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none"
                             stroke="currentColor" stroke-width="2"
                             stroke-linecap="round" stroke-linejoin="round">
                            <rect x="4" y="11" width="16" height="9" rx="2"/>
                            <path d="M8 11V7a4 4 0 1 1 8 0v4"/>
                        </svg>
                    </span>
                    <div class="min-w-0 flex-1">
                        <div class="text-sm font-semibold">Безопасность</div>
                        <div class="text-xs text-tg-muted truncate">
                            Подпись: <span class={signatureClass}>{signatureLabel}</span>
                            · {message.encrypted_payload_hex.length / 2} байт шифртекста
                        </div>
                    </div>
                    <svg class="w-4 h-4 text-tg-muted transition-transform shrink-0"
                         style="transform: rotate({securityOpen ? 180 : 0}deg)"
                         viewBox="0 0 24 24" fill="none" stroke="currentColor"
                         stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M6 9l6 6 6-6"/>
                    </svg>
                </button>

                {#if securityOpen}
                    <div class="border-t border-tg-divider px-3 py-3 space-y-3"
                         transition:slide={{ duration: 180 }}>
                        <div class="text-sm">
                            <span class="text-tg-muted">Статус подписи:</span>
                            <span class={signatureClass}>{signatureLabel}</span>
                        </div>

                        <div>
                            <div class="flex items-center justify-between mb-1.5">
                                <div class="text-xs uppercase tracking-wider text-tg-muted">
                                    Зашифрованный пакет
                                </div>
                                <button class="text-xs text-tg-accent hover:text-tg-accentHover transition"
                                        on:click={() => copy(message.encrypted_payload_hex)}>
                                    Копировать
                                </button>
                            </div>
                            <pre class="bg-tg-bg/60 border border-tg-divider rounded-xl px-3 py-2 text-xs
                                         font-mono text-tg-muted overflow-x-auto whitespace-pre-wrap break-all
                                         max-h-40">{message.encrypted_payload_hex}</pre>
                        </div>

                        <div>
                            <div class="flex items-center justify-between mb-1.5">
                                <div class="text-xs uppercase tracking-wider text-tg-muted">Nonce (8 байт)</div>
                                <button class="text-xs text-tg-accent hover:text-tg-accentHover transition"
                                        on:click={() => copy(message.nonce_hex)}>Копировать</button>
                            </div>
                            <pre class="bg-tg-bg/60 border border-tg-divider rounded-xl px-3 py-2 text-xs
                                         font-mono text-tg-muted whitespace-pre-wrap break-all">{message.nonce_hex}</pre>
                        </div>
                        <div>
                            <div class="flex items-center justify-between mb-1.5">
                                <div class="text-xs uppercase tracking-wider text-tg-muted">Подпись (64 байта)</div>
                                <button class="text-xs text-tg-accent hover:text-tg-accentHover transition"
                                        on:click={() => copy(message.signature_hex)}>Копировать</button>
                            </div>
                            <pre class="bg-tg-bg/60 border border-tg-divider rounded-xl px-3 py-2 text-xs
                                         font-mono text-tg-muted whitespace-pre-wrap break-all">{message.signature_hex}</pre>
                        </div>
                    </div>
                {/if}
            </section>
        </div>

        <footer class="px-5 py-3 border-t border-tg-divider flex justify-end">
            <button class="tg-button-ghost" on:click={close}>Закрыть</button>
        </footer>
    </div>
</div>
