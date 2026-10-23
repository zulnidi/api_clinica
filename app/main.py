from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routers
from app.application.ports import Clock
from app.domain.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)
from app.infrastructure.clock import SystemClock
from app.infrastructure.database import create_db_engine, create_session_factory
from app.settings import Settings

# Traducción de errores de dominio a códigos HTTP, en un solo lugar.
STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    ValidationError: 422,
    AuthenticationError: 401,
}


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    """App factory: permite crear la app con otra configuración o reloj (pruebas)."""
    settings = settings or Settings.from_env()
    engine = create_db_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        engine.dispose()  # libera las conexiones al apagar

    app = FastAPI(
        lifespan=lifespan,
        title="API Clínica",
        version="1.0.0",
        description="Gestión de pacientes, médicos y citas con reglas de agenda.",
    )
    app.state.settings = settings
    app.state.clock = clock or SystemClock()
    app.state.session_factory = create_session_factory(engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        code = STATUS_BY_ERROR.get(type(exc), 400)
        headers = {"WWW-Authenticate": "Bearer"} if code == 401 else None
        return JSONResponse({"detail": str(exc)}, status_code=code, headers=headers)

    for router in (
        routers.health,
        routers.auth,
        routers.patients,
        routers.doctors,
        routers.appointments,
    ):
        app.include_router(router)
    return app
