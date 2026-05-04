<script>
    import { onMount } from "svelte";
    import { fade } from "svelte/transition";

    import Login from "./routes/Login.svelte";
    import Register from "./routes/Register.svelte";
    import Chat from "./routes/Chat.svelte";

    import { path, navigate } from "./lib/router.js";
    import { isAuthenticated, theme } from "./lib/stores.js";

    // Любое изменение темы — отражаем на <html>, чтобы Tailwind (.dark)
    // переключил CSS-переменные.
    $: if (typeof document !== "undefined") {
        document.documentElement.classList.toggle("dark", $theme !== "light");
    }

    $: route =
        $path === "/register" ? "register" :
        $path === "/chat" ? "chat" :
        "login";

    // Простая защита маршрутов:
    //  • неавторизованный на /chat -> /
    //  • уже вошедший на /, /register -> /chat
    $: if (route === "chat" && !$isAuthenticated) {
        navigate("/", true);
    }
    $: if ((route === "login" || route === "register") && $isAuthenticated) {
        navigate("/chat", true);
    }

    onMount(() => {
        // если пришли по deep-link на /chat без токена — отправляем на /.
        if (window.location.pathname === "/chat" && !$isAuthenticated) {
            navigate("/", true);
        }
    });
</script>

{#key route}
    <div class="h-full" in:fade={{ duration: 220 }}>
        {#if route === "login"}
            <Login />
        {:else if route === "register"}
            <Register />
        {:else}
            <Chat />
        {/if}
    </div>
{/key}
