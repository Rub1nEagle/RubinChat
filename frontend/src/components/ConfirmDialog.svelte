<script>
    import { createEventDispatcher } from "svelte";
    import { fade, fly } from "svelte/transition";

    export let open = false;
    export let title = "Подтвердите действие";
    export let message = "";
    export let confirmText = "Подтвердить";
    export let cancelText = "Отмена";
    /** "danger" окрашивает кнопку подтверждения в красный. */
    export let variant = "default"; // "default" | "danger"

    const dispatch = createEventDispatcher();

    function confirm() {
        dispatch("confirm");
    }
    function cancel() {
        dispatch("cancel");
    }

    function onKey(e) {
        if (!open) return;
        if (e.key === "Escape") {
            e.preventDefault();
            cancel();
        } else if (e.key === "Enter") {
            e.preventDefault();
            confirm();
        }
    }
</script>

<svelte:window on:keydown={onKey} />

{#if open}
    <div class="fixed inset-0 z-[60] grid place-items-center px-4"
         in:fade={{ duration: 120 }} out:fade={{ duration: 100 }}>
        <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"
             on:click={cancel}></div>

        <div class="relative w-full max-w-sm tg-card rounded-2xl p-5"
             in:fly={{ y: 8, duration: 160 }}>
            <div class="font-semibold text-base mb-2">{title}</div>
            {#if message}
                <p class="text-sm text-tg-text/85 leading-relaxed mb-4">{message}</p>
            {/if}
            <div class="flex gap-2 justify-end">
                <button type="button" class="tg-button-ghost" on:click={cancel}>
                    {cancelText}
                </button>
                <button type="button"
                        class="tg-button {variant === 'danger'
                            ? 'bg-tg-danger hover:bg-tg-danger/90 shadow-none'
                            : ''}"
                        on:click={confirm}>
                    {confirmText}
                </button>
            </div>
        </div>
    </div>
{/if}
