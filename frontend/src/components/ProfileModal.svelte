<script>
    import { createEventDispatcher, onMount } from "svelte";
    import { fade, fly, slide } from "svelte/transition";

    import Avatar from "./Avatar.svelte";
    import PasswordInput from "./PasswordInput.svelte";
    import { users as usersApi, auth as authApi, crypto as cryptoApi } from "../lib/api.js";
    import { compressImage } from "../lib/image.js";
    import {
        displayName, lastSeen, groupHex,
    } from "../lib/format.js";
    import { conversations, session, logout } from "../lib/stores.js";
    import { navigate } from "../lib/router.js";

    /** @type {number} */
    export let userId;
    /** Если true — это профиль владельца сессии и его можно редактировать. */
    export let editable = false;

    const dispatch = createEventDispatcher();

    let user = null;
    let loading = true;
    let error = "";
    let mutualFingerprint = "";   // safety number — общий для обоих собеседников
    let securityOpen = false;     // секция «Безопасность» свёрнута по умолчанию

    // Состояние формы редактирования.
    let editingProfile = false;
    let formDisplayName = "";
    let formBio = "";
    let saving = false;
    let saveError = "";

    // Смена пароля.
    let pwOpen = false;
    let pwCurrent = "";
    let pwNew = "";
    let pwNewRepeat = "";
    let pwSaving = false;
    let pwError = "";
    let pwSuccess = "";

    // Удаление аккаунта.
    let delOpen = false;
    let delPassword = "";
    let delError = "";
    let delDoing = false;

    // Аватар.
    let avatarBusy = false;
    let avatarError = "";
    let avatarFileInput;

    onMount(load);

    async function load() {
        loading = true;
        error = "";
        try {
            user = editable ? await usersApi.me() : await usersApi.profile(userId);
            formDisplayName = user.display_name || "";
            formBio = user.bio || "";
            // Для собеседника считаем общий safety-number обеих сторон —
            // именно его нужно сравнивать визуально / голосом.
            if (!editable) {
                try {
                    const r = await cryptoApi.fingerprint(userId);
                    mutualFingerprint = r.fingerprint_hex;
                } catch (_) {
                    mutualFingerprint = "";
                }
            }
        } catch (e) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    async function save() {
        saving = true;
        saveError = "";
        try {
            user = await usersApi.updateMe({
                display_name: formDisplayName,
                bio: formBio,
            });
            // Обновим в локальной сессии при необходимости.
            session.update(($s) =>
                $s ? { ...$s, username: user.username } : $s
            );
            editingProfile = false;
        } catch (e) {
            saveError = e.message;
        } finally {
            saving = false;
        }
    }

    function close() {
        dispatch("close");
    }

    function copy(text) {
        try { navigator.clipboard.writeText(text); } catch (_) {}
    }

    async function changePassword() {
        pwError = "";
        pwSuccess = "";
        if (pwNew.length < 8) {
            pwError = "Новый пароль должен быть не короче 8 символов.";
            return;
        }
        if (pwNew !== pwNewRepeat) {
            pwError = "Подтверждение пароля не совпадает.";
            return;
        }
        pwSaving = true;
        try {
            const data = await authApi.changePassword({
                currentPassword: pwCurrent,
                newPassword: pwNew,
            });
            // Сервер вернул новый JWT и расшифрованный приватный ключ —
            // освежаем сессию в localStorage.
            session.set({
                token: data.access_token,
                user_id: data.user_id,
                username: data.username,
                private_key_hex: data.private_key_hex,
            });
            pwCurrent = pwNew = pwNewRepeat = "";
            pwOpen = false;
            pwSuccess = "Пароль обновлён.";
        } catch (e) {
            pwError = e.message;
        } finally {
            pwSaving = false;
        }
    }

    async function onAvatarPick(e) {
        const f = e.target.files?.[0];
        e.target.value = "";
        if (!f) return;
        avatarError = "";
        avatarBusy = true;
        try {
            const compressed = await compressImage(f);
            user = await usersApi.uploadAvatar(compressed);
        } catch (err) {
            avatarError = err.message || "не удалось загрузить";
        } finally {
            avatarBusy = false;
        }
    }

    async function removeAvatar() {
        avatarError = "";
        avatarBusy = true;
        try {
            user = await usersApi.removeAvatar();
        } catch (err) {
            avatarError = err.message || "не удалось удалить";
        } finally {
            avatarBusy = false;
        }
    }

    async function deleteAccount() {
        delError = "";
        if (!delPassword) {
            delError = "Введите пароль для подтверждения.";
            return;
        }
        delDoing = true;
        try {
            await authApi.deleteAccount({ password: delPassword });
            logout();
            navigate("/", true);
        } catch (e) {
            delError = e.message;
        } finally {
            delDoing = false;
        }
    }

    // Статистика переписки (только для собеседника).
    $: peerSummary = !editable && user ? $conversations[user.user_id] : null;
    $: createdLocal = user
        ? new Date(user.created_at).toLocaleDateString("ru-RU", {
              day: "numeric", month: "long", year: "numeric",
          })
        : "";
</script>

<div class="fixed inset-0 z-50 grid place-items-end sm:place-items-center px-0 sm:px-4 py-0 sm:py-6"
     in:fade={{ duration: 150 }} out:fade={{ duration: 120 }}>
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
    <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" on:click={close}></div>

    <div class="relative w-full max-w-xl tg-card animate-modal-in
                rounded-b-none sm:rounded-2xl
                max-h-[92vh] sm:max-h-[88vh] overflow-y-auto"
         in:fly={{ y: 12, duration: 180 }}>

        <!-- Шапка -->
        <header class="flex items-center justify-between px-5 py-4 border-b border-tg-divider">
            <div class="font-semibold text-lg">
                {editable ? "Мой профиль" : "Профиль собеседника"}
            </div>
            <button class="text-tg-muted hover:text-tg-text p-2 rounded-full hover:bg-tg-text/5"
                    on:click={close} title="Закрыть">
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 6L6 18"/><path d="M6 6l12 12"/>
                </svg>
            </button>
        </header>

        {#if loading}
            <div class="px-5 py-12 text-center text-tg-muted text-sm">Загрузка профиля…</div>
        {:else if error}
            <div class="px-5 py-12 text-center text-tg-danger text-sm">{error}</div>
        {:else if user}
            <!-- Идентичность -->
            <section class="px-5 py-5 flex items-center gap-4 border-b border-tg-divider">
                <div class="relative">
                    <Avatar name={displayName(user)} size={72}
                            userId={user.user_id}
                            hasAvatar={user.has_avatar}
                            avatarVersion={user.avatar_version || 0}
                            online={user.is_online} showOnlineDot />
                    {#if editable}
                        <input type="file" accept="image/jpeg,image/png,image/webp"
                               bind:this={avatarFileInput}
                               on:change={onAvatarPick}
                               class="hidden" />
                        <button class="absolute -bottom-1 -right-1 w-7 h-7 rounded-full
                                       bg-tg-accent text-white grid place-items-center
                                       hover:bg-tg-accentHover shadow-ruby
                                       disabled:opacity-50"
                                disabled={avatarBusy}
                                title="Сменить аватар"
                                on:click={() => avatarFileInput?.click()}>
                            {#if avatarBusy}
                                <span class="typing-dot"></span>
                            {:else}
                                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                                    <circle cx="12" cy="13" r="4"/>
                                </svg>
                            {/if}
                        </button>
                    {/if}
                </div>
                <div class="min-w-0 flex-1">
                    <div class="text-xl font-semibold truncate">{displayName(user)}</div>
                    <div class="text-sm text-tg-muted truncate">@{user.username}</div>
                    <div class="text-xs mt-1">
                        {#if user.is_online}
                            <span class="inline-flex items-center gap-1 text-tg-success">
                                <span class="inline-block w-1.5 h-1.5 rounded-full bg-tg-success"></span>
                                в сети
                            </span>
                        {:else}
                            <span class="text-tg-muted">{lastSeen(user.last_seen_at, false)}</span>
                        {/if}
                    </div>
                    {#if editable && user.has_avatar}
                        <button class="text-xs text-tg-muted hover:text-tg-danger mt-1
                                       transition-colors"
                                disabled={avatarBusy}
                                on:click={removeAvatar}>
                            Удалить аватар
                        </button>
                    {/if}
                    {#if avatarError}
                        <div class="text-xs text-tg-danger mt-1">{avatarError}</div>
                    {/if}
                </div>
            </section>

            <!-- Био / редактирование -->
            {#if editable && editingProfile}
                <section class="px-5 py-4 border-b border-tg-divider space-y-3">
                    <label class="block">
                        <span class="text-xs uppercase tracking-wider text-tg-muted">Имя</span>
                        <input class="tg-input mt-1"
                               bind:value={formDisplayName}
                               maxlength="120"
                               placeholder={user.username} />
                    </label>
                    <label class="block">
                        <span class="text-xs uppercase tracking-wider text-tg-muted">О себе</span>
                        <textarea class="tg-input mt-1 resize-none" rows="3"
                                  maxlength="500"
                                  bind:value={formBio}
                                  placeholder="Несколько слов о себе"></textarea>
                    </label>
                    {#if saveError}
                        <p class="text-sm text-tg-danger">{saveError}</p>
                    {/if}
                    <div class="flex gap-2 justify-end pt-1">
                        <button class="tg-button-ghost"
                                on:click={() => (editingProfile = false)}
                                disabled={saving}>
                            Отмена
                        </button>
                        <button class="tg-button" on:click={save} disabled={saving}>
                            {saving ? "Сохраняем…" : "Сохранить"}
                        </button>
                    </div>
                </section>
            {:else}
                <section class="px-5 py-4 border-b border-tg-divider">
                    <div class="text-xs uppercase tracking-wider text-tg-muted mb-1.5">О себе</div>
                    <div class="text-sm whitespace-pre-wrap text-tg-text/90">
                        {user.bio || (editable ? "Пока ничего не написано." : "Собеседник пока не оставил подпись.")}
                    </div>
                    <div class="text-xs text-tg-muted mt-3">
                        Аккаунт зарегистрирован {createdLocal}
                    </div>
                    {#if editable}
                        <button class="mt-3 tg-button-ghost text-sm"
                                on:click={() => (editingProfile = true)}>
                            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none"
                                 stroke="currentColor" stroke-width="2"
                                 stroke-linecap="round" stroke-linejoin="round">
                                <path d="M12 20h9"/>
                                <path d="M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
                            </svg>
                            Редактировать профиль
                        </button>
                    {/if}
                </section>
            {/if}

            <!-- Статистика переписки -->
            {#if !editable && peerSummary}
                <section class="px-5 py-4 border-b border-tg-divider">
                    <div class="text-xs uppercase tracking-wider text-tg-muted mb-2">
                        Переписка
                    </div>
                    <div class="grid grid-cols-2 gap-3 text-sm">
                        {#if peerSummary.last_message}
                            <div>
                                <div class="text-xs text-tg-muted">Последнее сообщение</div>
                                <div>{new Date(peerSummary.last_message.created_at)
                                        .toLocaleString("ru-RU")}</div>
                            </div>
                        {/if}
                        {#if peerSummary.unread_count > 0}
                            <div>
                                <div class="text-xs text-tg-muted">Непрочитано</div>
                                <div class="text-tg-accent font-medium">
                                    {peerSummary.unread_count}
                                </div>
                            </div>
                        {/if}
                    </div>
                </section>
            {/if}

            <!-- Безопасность — свёрнутая по умолчанию -->
            <section class="px-5 py-4">
                <button type="button"
                        class="w-full flex items-center gap-2 -mx-2 px-2 py-2 rounded-lg
                               hover:bg-tg-text/5 transition-colors text-left"
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
                        <div class="text-xs text-tg-muted">
                            {editable
                                ? "Алгоритмы и ваш публичный ключ"
                                : "Алгоритмы, отпечаток разговора и публичный ключ собеседника"}
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
                    <div class="mt-4 space-y-4" transition:slide={{ duration: 180 }}>
                        <dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                            <div>
                                <dt class="text-xs uppercase tracking-wider text-tg-muted">Шифрование</dt>
                                <dd>ГОСТ 28147-89 · CTR</dd>
                            </div>
                            <div>
                                <dt class="text-xs uppercase tracking-wider text-tg-muted">Подпись</dt>
                                <dd>ГОСТ 34.10-2012 · 256 бит</dd>
                            </div>
                            <div>
                                <dt class="text-xs uppercase tracking-wider text-tg-muted">Хеш</dt>
                                <dd>Стрибог-256</dd>
                            </div>
                            <div>
                                <dt class="text-xs uppercase tracking-wider text-tg-muted">Длина ключа</dt>
                                <dd>{user.public_key_hex.length / 2} байт ({user.public_key_hex.length * 4} бит)</dd>
                            </div>
                        </dl>

                        {#if !editable && mutualFingerprint}
                            <!-- Совместный safety-number, как в Signal: оба собеседника
                                 видят одинаковый код. Если он совпал — MITM нет. -->
                            <div>
                                <div class="flex items-center justify-between mb-1.5">
                                    <div class="text-xs uppercase tracking-wider text-tg-muted">
                                        Отпечаток разговора
                                    </div>
                                    <button class="text-xs text-tg-accent hover:text-tg-accentHover transition"
                                            on:click={() => copy(mutualFingerprint)}>
                                        Копировать
                                    </button>
                                </div>
                                <pre class="bg-tg-bg/60 border border-tg-divider rounded-xl px-3 py-2 text-sm
                                             font-mono tracking-wider text-tg-text/90">{groupHex(mutualFingerprint, 8, 4)}</pre>
                                <div class="text-[11px] text-tg-muted mt-1">
                                    Сравните этот код с тем, что видит {displayName(user)} в вашем профиле.
                                    Если совпало — канал безопасен.
                                </div>
                            </div>
                        {/if}

                        <div>
                            <div class="flex items-center justify-between mb-1.5">
                                <div class="text-xs uppercase tracking-wider text-tg-muted">
                                    {editable ? "Ваш публичный ключ" : "Публичный ключ собеседника"}
                                </div>
                                <button class="text-xs text-tg-accent hover:text-tg-accentHover transition"
                                        on:click={() => copy(user.public_key_hex)}>
                                    Копировать ключ
                                </button>
                            </div>
                            <pre class="bg-tg-bg/60 border border-tg-divider rounded-xl px-3 py-2 text-sm
                                         font-mono tracking-wider text-tg-text/90">{groupHex(user.public_key_hex, 8, 4)}</pre>
                        </div>
                    </div>
                {/if}
            </section>

            <!-- Учётная запись (только для своего профиля) -->
            {#if editable}
                <section class="px-5 py-4 border-t border-tg-divider space-y-3">
                    <div class="text-xs uppercase tracking-wider text-tg-muted">
                        Учётная запись
                    </div>

                    <!-- Смена пароля -->
                    {#if !pwOpen}
                        <div class="flex items-center justify-between gap-3">
                            <div>
                                <div class="text-sm font-medium">Сменить пароль</div>
                                <div class="text-xs text-tg-muted">
                                    Приватный ключ будет перешифрован новым паролем.
                                </div>
                            </div>
                            <button class="tg-button-ghost text-sm shrink-0"
                                    on:click={() => { pwOpen = true; pwError = ""; pwSuccess = ""; }}>
                                Изменить
                            </button>
                        </div>
                        {#if pwSuccess}
                            <p class="text-xs text-tg-success">{pwSuccess}</p>
                        {/if}
                    {:else}
                        <div class="space-y-2">
                            <!-- svelte-ignore a11y-label-has-associated-control -->
                            <label class="block">
                                <span class="text-xs uppercase tracking-wider text-tg-muted">Текущий пароль</span>
                                <div class="mt-1">
                                    <PasswordInput bind:value={pwCurrent}
                                                   autocomplete="current-password" />
                                </div>
                            </label>
                            <!-- svelte-ignore a11y-label-has-associated-control -->
                            <label class="block">
                                <span class="text-xs uppercase tracking-wider text-tg-muted">Новый пароль</span>
                                <div class="mt-1">
                                    <PasswordInput bind:value={pwNew}
                                                   autocomplete="new-password" minlength={8} />
                                </div>
                            </label>
                            <!-- svelte-ignore a11y-label-has-associated-control -->
                            <label class="block">
                                <span class="text-xs uppercase tracking-wider text-tg-muted">Повторите новый</span>
                                <div class="mt-1">
                                    <PasswordInput bind:value={pwNewRepeat}
                                                   autocomplete="new-password" minlength={8} />
                                </div>
                            </label>
                            {#if pwError}
                                <p class="text-sm text-tg-danger">{pwError}</p>
                            {/if}
                            <div class="flex gap-2 justify-end pt-1">
                                <button class="tg-button-ghost"
                                        on:click={() => { pwOpen = false; pwCurrent = pwNew = pwNewRepeat = ""; pwError = ""; }}
                                        disabled={pwSaving}>
                                    Отмена
                                </button>
                                <button class="tg-button" on:click={changePassword} disabled={pwSaving}>
                                    {pwSaving ? "Сохраняем…" : "Сменить пароль"}
                                </button>
                            </div>
                        </div>
                    {/if}

                    <!-- Удаление аккаунта -->
                    <div class="border-t border-tg-divider pt-3">
                        {#if !delOpen}
                            <div class="flex items-center justify-between gap-3">
                                <div>
                                    <div class="text-sm font-medium text-tg-danger">Удалить аккаунт</div>
                                    <div class="text-xs text-tg-muted">
                                        Будут безвозвратно удалены ваш профиль и все сообщения.
                                    </div>
                                </div>
                                <button class="tg-button-ghost text-sm text-tg-danger hover:text-tg-danger shrink-0"
                                        on:click={() => { delOpen = true; delError = ""; }}>
                                    Удалить
                                </button>
                            </div>
                        {:else}
                            <div class="space-y-2">
                                <p class="text-sm">
                                    Подтвердите паролем. После удаления восстановить аккаунт нельзя.
                                </p>
                                <PasswordInput bind:value={delPassword}
                                               autocomplete="current-password"
                                               placeholder="Ваш пароль" />
                                {#if delError}
                                    <p class="text-sm text-tg-danger">{delError}</p>
                                {/if}
                                <div class="flex gap-2 justify-end pt-1">
                                    <button class="tg-button-ghost"
                                            on:click={() => { delOpen = false; delPassword = ""; delError = ""; }}
                                            disabled={delDoing}>
                                        Отмена
                                    </button>
                                    <button class="tg-button bg-tg-danger hover:bg-tg-danger/90 shadow-none"
                                            on:click={deleteAccount} disabled={delDoing}>
                                        {delDoing ? "Удаляем…" : "Удалить безвозвратно"}
                                    </button>
                                </div>
                            </div>
                        {/if}
                    </div>
                </section>
            {/if}
        {/if}

        <footer class="px-5 py-3 border-t border-tg-divider flex justify-end">
            <button class="tg-button-ghost" on:click={close}>Закрыть</button>
        </footer>
    </div>
</div>
