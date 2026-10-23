"""Punto de composición: aquí se eligen las implementaciones concretas de cada puerto."""

from collections.abc import Iterator
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.services import AppointmentService, AuthService, DoctorService, PatientService
from app.domain.entities import User
from app.domain.errors import AuthenticationError
from app.infrastructure.repositories import (
    SqlAppointmentRepository,
    SqlDoctorRepository,
    SqlPatientRepository,
    SqlUserRepository,
)
from app.infrastructure.security import JwtTokenService, ScryptPasswordHasher

bearer = HTTPBearer(auto_error=False)


def get_session(request: Request) -> Iterator[Session]:
    """Una sesión por petición: confirma si todo salió bien y revierte si hubo error."""
    session: Session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_auth_service(request: Request, session: Session = Depends(get_session)) -> AuthService:
    settings = request.app.state.settings
    tokens = JwtTokenService(
        settings.jwt_secret,
        timedelta(minutes=settings.jwt_expires_minutes),
        request.app.state.clock,
    )
    return AuthService(SqlUserRepository(session), ScryptPasswordHasher(), tokens)


def get_patient_service(session: Session = Depends(get_session)) -> PatientService:
    return PatientService(SqlPatientRepository(session))


def get_doctor_service(session: Session = Depends(get_session)) -> DoctorService:
    return DoctorService(SqlDoctorRepository(session))


def get_appointment_service(
    request: Request,
    session: Session = Depends(get_session),
    patients: PatientService = Depends(get_patient_service),
    doctors: DoctorService = Depends(get_doctor_service),
) -> AppointmentService:
    return AppointmentService(
        SqlAppointmentRepository(session),
        patients,
        doctors,
        request.app.state.clock,
        ZoneInfo(request.app.state.settings.clinic_timezone),
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    auth: AuthService = Depends(get_auth_service),
) -> User:
    if credentials is None:
        raise AuthenticationError("Falta el token de autenticación.")
    return auth.authenticate(credentials.credentials)
