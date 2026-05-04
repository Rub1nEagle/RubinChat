<script>
    export let title = "RubinChat";
    export let subtitle = "Защищённый мессенджер";
</script>

<div class="min-h-full grid place-items-center px-4 py-10">
    <div class="w-full max-w-md tg-card p-8 animate-pop">
        <div class="flex flex-col items-center mb-6 select-none">
            <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-tg-accent to-tg-accentDeep
                        grid place-items-center shadow-ruby mb-4 rotate-3">
                <!-- Стилизованный гранёный рубин -->
                <svg viewBox="0 0 24 24" class="w-9 h-9 text-white -rotate-3" fill="none">
                    <path d="M5 9 L8 4 L16 4 L19 9 L12 21 Z" fill="currentColor" opacity="0.95"/>
                    <path d="M5 9 L12 9 L8 4 Z" fill="white" opacity="0.18"/>
                    <path d="M19 9 L12 9 L16 4 Z" fill="black" opacity="0.20"/>
                    <path d="M12 9 L12 21" stroke="white" stroke-opacity="0.25" stroke-width="0.6"/>
                </svg>
            </div>
            <h1 class="text-2xl font-bold tracking-tight">{title}</h1>
            <p class="text-sm text-tg-muted mt-1">{subtitle}</p>
        </div>

        <slot />
    </div>
</div>
