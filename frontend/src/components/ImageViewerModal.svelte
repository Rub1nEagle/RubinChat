<script>
    import { createEventDispatcher, onMount, onDestroy } from "svelte";
    import { fade, scale } from "svelte/transition";
    import { portal } from "../lib/portal.js";

    /** Готовый blob-URL уже расшифрованной картинки (обязателен). */
    export let url;
    export let alt = "Вложение";

    const dispatch = createEventDispatcher();

    function close() {
        dispatch("close");
    }

    function onKey(e) {
        if (e.key === "Escape") close();
    }

    // Пока модалка открыта — глушим scroll body, чтобы фон не ёрзал.
    let prevOverflow = "";
    onMount(() => {
        prevOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        window.addEventListener("keydown", onKey);
    });
    onDestroy(() => {
        document.body.style.overflow = prevOverflow;
        window.removeEventListener("keydown", onKey);
    });
</script>

<div use:portal>
    <div class="fixed inset-0 z-[60] grid place-items-center"
         in:fade={{ duration: 120 }} out:fade={{ duration: 100 }}>
        <!-- Затемнённый бэкдроп: клик закрывает. -->
        <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
        <div class="absolute inset-0 bg-black/85 backdrop-blur-sm"
             on:click={close}></div>

        <!-- Кнопка закрытия — поверх картинки, в правом верхнем углу. -->
        <button class="absolute top-3 right-3 z-10
                       w-10 h-10 rounded-full bg-black/50 hover:bg-black/70
                       text-white grid place-items-center transition"
                on:click={close} aria-label="Закрыть">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M18 6L6 18"/><path d="M6 6l12 12"/>
            </svg>
        </button>

        <!-- Сама картинка: ограничена вьюпортом, кликом по ней не закрываем
             (чтобы можно было выделить/перетащить). -->
        <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-noninteractive-element-interactions -->
        <img src={url}
             alt={alt}
             class="relative max-w-[95vw] max-h-[92vh] object-contain
                    rounded-lg shadow-2xl select-none"
             on:click|stopPropagation
             in:scale={{ duration: 160, start: 0.92 }}
             out:fade={{ duration: 100 }} />
    </div>
</div>
