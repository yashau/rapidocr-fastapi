from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Response
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .api import router as api_router
from .auth import require_api_key
from .config import get_settings
from .ocr import OCRService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    app.state.ocr_service = OCRService(settings)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    _ = settings.api_keys
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Queued RapidOCR service for PNG/JPEG image OCR.",
        lifespan=lifespan,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.include_router(api_router, prefix="/v1", tags=["ocr"])

    @app.get("/healthz", tags=["system"])
    async def healthz():
        return {"ok": True}

    @app.get("/readyz", tags=["system"])
    async def readyz():
        return {"ready": True}

    if settings.enable_metrics:
        dependencies = [Depends(require_api_key)] if settings.metrics_require_api_key else []

        @app.get("/metrics", tags=["system"], dependencies=dependencies)
        async def metrics():
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    if settings.webui_dir and settings.webui_dir.exists():
        app.mount("/", StaticFiles(directory=settings.webui_dir, html=True), name="webui")

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=settings.app_name,
            version=settings.app_version,
            description="Queued RapidOCR service for PNG/JPEG image OCR.",
            routes=app.routes,
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {}).update(
            {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                },
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                },
            }
        )
        for path, methods in schema.get("paths", {}).items():
            if path == "/metrics" and not settings.metrics_require_api_key:
                continue
            if path in {"/healthz", "/readyz", "/openapi.json"}:
                continue
            for operation in methods.values():
                if isinstance(operation, dict):
                    operation.setdefault("security", [{"ApiKeyAuth": []}, {"BearerAuth": []}])
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi

    return app


app = create_app()


def run() -> None:
    uvicorn.run("rapidocr_api.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
