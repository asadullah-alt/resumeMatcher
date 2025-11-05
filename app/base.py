import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .api import health_check, v1_router, RequestIDMiddleware
from .core import (
    settings,
    init_db,
    close_db,
    setup_logging,
    custom_http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
# models are Beanie documents and will be initialized by init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MongoDB / Beanie
    await init_db(app)
    try:
        yield
    finally:
        await close_db()


def create_app() -> FastAPI:
    """
    configure and create the FastAPI application instance.
    """
    setup_logging()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY, same_site="lax"
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    app.add_exception_handler(HTTPException, custom_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    if os.path.exists(settings.FRONTEND_PATH):
        app.mount(
            "/app",
            StaticFiles(directory=settings.FRONTEND_PATH, html=True),
            name=settings.PROJECT_NAME,
        )

    app.include_router(health_check)
    app.include_router(v1_router)

    return app
