<script>
    export let value = "";
    export let placeholder = "";
    export let autocomplete = "current-password";
    export let minlength = undefined;
    export let maxlength = undefined;
    export let required = false;
    export let disabled = false;
    export let name = undefined;

    let show = false;
</script>

<div class="relative">
    <!-- Svelte не разрешает dynamic `type` вместе с `bind:value`,
         поэтому проброс делаем вручную. -->
    <input
        class="tg-input pr-11"
        type={show ? "text" : "password"}
        value={value ?? ""}
        on:input={(e) => (value = e.currentTarget.value)}
        on:keydown
        {autocomplete}
        {required}
        {minlength}
        {maxlength}
        {disabled}
        {name}
        {placeholder}
    />
    <button
        type="button"
        tabindex="-1"
        class="absolute inset-y-0 right-0 px-3 flex items-center
               text-tg-muted hover:text-tg-text transition-colors"
        on:click={() => (show = !show)}
        aria-label={show ? "Скрыть пароль" : "Показать пароль"}
        title={show ? "Скрыть пароль" : "Показать пароль"}
    >
        {#if show}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                 stroke-linecap="round" stroke-linejoin="round" class="w-5 h-5">
                <path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-6.5 0-10-7-10-7a19.5 19.5 0 0 1 4.06-5.06"/>
                <path d="M9.9 4.24A11 11 0 0 1 12 4c6.5 0 10 7 10 7a19.62 19.62 0 0 1-3.17 4.31"/>
                <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/>
                <line x1="2" y1="2" x2="22" y2="22"/>
            </svg>
        {:else}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                 stroke-linecap="round" stroke-linejoin="round" class="w-5 h-5">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/>
                <circle cx="12" cy="12" r="3"/>
            </svg>
        {/if}
    </button>
</div>
