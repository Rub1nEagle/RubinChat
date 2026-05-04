<script>
    import { fade } from "svelte/transition";
    import AuthLayout from "../components/AuthLayout.svelte";
    import PasswordInput from "../components/PasswordInput.svelte";
    import { auth } from "../lib/api.js";
    import { session } from "../lib/stores.js";
    import { navigate } from "../lib/router.js";

    let username = "";
    let password = "";
    let loading = false;
    let error = "";

    function onEnter(e) {
        if (e.key === "Enter" && !e.shiftKey && !loading) {
            e.preventDefault();
            submit();
        }
    }

    async function submit() {
        if (loading) return;
        error = "";
        loading = true;
        try {
            const data = await auth.register({ username, password });
            session.set({
                token: data.access_token,
                user_id: data.user_id,
                username: data.username,
                private_key_hex: data.private_key_hex,
            });
            // Жёсткий redirect: гарантирует свежий mount чата
            // с сессией из localStorage. То же что и в Login.svelte.
            window.location.replace("/chat");
        } catch (e) {
            error = e.message;
            loading = false;
        }
    }
</script>

<AuthLayout title="Создание аккаунта" subtitle="Криптографические ключи будут сгенерированы автоматически">
    <form on:submit|preventDefault={submit} class="space-y-3">
        <label class="block">
            <span class="text-xs uppercase tracking-wider text-tg-muted">Имя пользователя</span>
            <input
                class="tg-input mt-1"
                bind:value={username}
                on:keydown={onEnter}
                autocomplete="username"
                required
                minlength="3"
                maxlength="64"
                pattern="[A-Za-z0-9_.\-]+"
                placeholder="alice"
            />
        </label>

        <!-- svelte-ignore a11y-label-has-associated-control -->
        <label class="block">
            <span class="text-xs uppercase tracking-wider text-tg-muted">Пароль</span>
            <div class="mt-1">
                <PasswordInput
                    bind:value={password}
                    on:keydown={onEnter}
                    autocomplete="new-password"
                    required
                    minlength={8}
                    placeholder="не короче 8 символов"
                />
            </div>
        </label>

        <p class="text-xs text-tg-muted leading-relaxed">
            Приватный ключ зашифровывается вашим паролем; сервер хранит только
            bcrypt-хеш и не способен восстановить ключ без вашего повторного входа.
        </p>

        {#if error}
            <p class="text-sm text-tg-danger" in:fade={{ duration: 150 }}>{error}</p>
        {/if}

        <button type="submit" class="tg-button w-full mt-2" disabled={loading}>
            {#if loading}
                <span class="typing-dot" />
                <span class="typing-dot" style="animation-delay: 0.15s" />
                <span class="typing-dot" style="animation-delay: 0.30s" />
            {:else}
                Создать аккаунт
            {/if}
        </button>

        <p class="text-sm text-tg-muted text-center pt-3">
            Уже зарегистрированы?
            <button type="button"
                    class="text-tg-accent hover:text-tg-accentHover transition-colors"
                    on:click={() => navigate("/")}>
                Войти
            </button>
        </p>
    </form>
</AuthLayout>
