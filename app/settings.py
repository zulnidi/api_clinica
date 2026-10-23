import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    database_url: str = "sqlite:///./clinic.db"
    jwt_expires_minutes: int = 60
    clinic_timezone: str = "America/Bogota"
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)

    @classmethod
    def from_env(cls) -> "Settings":
        secret = os.environ.get("JWT_SECRET")
        if not secret or len(secret) < 32:
            raise RuntimeError("Define JWT_SECRET (mínimo 32 caracteres) en el entorno.")
        return cls(
            jwt_secret=secret,
            database_url=os.environ.get("DATABASE_URL", cls.database_url),
            jwt_expires_minutes=int(os.environ.get("JWT_EXPIRES_MINUTES", cls.jwt_expires_minutes)),
            clinic_timezone=os.environ.get("CLINIC_TIMEZONE", cls.clinic_timezone),
            cors_origins=tuple(
                o.strip() for o in os.environ.get("CORS_ORIGINS", cls.cors_origins[0]).split(",")
            ),
        )
