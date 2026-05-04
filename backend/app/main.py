"""FastAPI application entry point."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.error_translations import translate_validation_errors
from .api.routes import api_router
from .core.config import get_settings
from .websocket import ws_router


def _find_frontend_dist() -> Path | None:
    """Discover where the built Svelte SPA lives.

    Two layouts are supported:
      • inside the Docker image — `/frontend/dist`;
      • during local development — `<repo>/frontend/dist` next to backend/.
    """
    candidates = [
        Path("/frontend/dist"),
        Path(__file__).resolve().parents[2] / "frontend" / "dist",
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return None


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(ws_router)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Перевод pydantic-ошибок на русский, чтобы UI показывал
        пользователю понятный текст без отдельного маппинга на клиенте."""
        translated = translate_validation_errors(exc.errors())
        # Дополнительно: первое сообщение кладём как `detail` (строка),
        # потому что фронт у нас часто читает именно его в showToast.
        first_msg = translated[0]["msg"] if translated else "Неверные данные запроса"
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": first_msg, "errors": translated},
        )

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    dist = _find_frontend_dist()
    if dist is not None:
        # Vite emits /assets/* — long-cacheable hashed bundles.
        assets_dir = dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/favicon.ico", include_in_schema=False)
        async def favicon() -> FileResponse:
            ico = dist / "favicon.ico"
            if not ico.is_file():
                raise HTTPException(status_code=404)
            return FileResponse(ico)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            """SPA fallback: serve any matching static file, or index.html."""
            # Технические префиксы должны отдавать честный 404, а не SPA.
            if full_path.startswith(("api/", "ws", "docs", "redoc", "openapi.json")):
                raise HTTPException(status_code=404)
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
