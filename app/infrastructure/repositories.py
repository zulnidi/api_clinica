"""Implementaciones SQLAlchemy de los puertos de repositorio."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.domain.entities import Appointment, AppointmentStatus, Doctor, Patient, User
from app.infrastructure.database import (
    AppointmentModel,
    DoctorModel,
    PatientModel,
    UserModel,
)


def _to_naive_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


def _to_aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC)


class SqlUserRepository:
    def __init__(self, session: Session):
        self._s = session

    @staticmethod
    def _entity(m: UserModel) -> User:
        return User(m.id, m.email, m.password_hash)

    def add(self, user: User) -> User:
        model = UserModel(email=user.email, password_hash=user.password_hash)
        self._s.add(model)
        self._s.flush()
        return self._entity(model)

    def get_by_email(self, email: str) -> User | None:
        model = self._s.scalar(select(UserModel).where(UserModel.email == email))
        return self._entity(model) if model else None

    def get(self, user_id: int) -> User | None:
        model = self._s.get(UserModel, user_id)
        return self._entity(model) if model else None


class SqlPatientRepository:
    def __init__(self, session: Session):
        self._s = session

    @staticmethod
    def _entity(m: PatientModel) -> Patient:
        return Patient(m.id, m.full_name, m.document_id, m.email, m.phone)

    def add(self, patient: Patient) -> Patient:
        model = PatientModel(
            full_name=patient.full_name,
            document_id=patient.document_id,
            email=patient.email,
            phone=patient.phone,
        )
        self._s.add(model)
        self._s.flush()
        return self._entity(model)

    def get(self, patient_id: int) -> Patient | None:
        model = self._s.get(PatientModel, patient_id)
        return self._entity(model) if model else None

    def get_by_document(self, document_id: str) -> Patient | None:
        model = self._s.scalar(select(PatientModel).where(PatientModel.document_id == document_id))
        return self._entity(model) if model else None

    def update(self, patient: Patient) -> Patient:
        model = self._s.get(PatientModel, patient.id)
        model.full_name, model.email, model.phone = patient.full_name, patient.email, patient.phone
        self._s.flush()
        return self._entity(model)

    def list(self, *, query: str | None, limit: int, offset: int) -> list[Patient]:
        stmt = select(PatientModel).order_by(PatientModel.id).limit(limit).offset(offset)
        if query:
            stmt = stmt.where(PatientModel.full_name.ilike(f"%{query}%"))
        return [self._entity(m) for m in self._s.scalars(stmt)]


class SqlDoctorRepository:
    def __init__(self, session: Session):
        self._s = session

    @staticmethod
    def _entity(m: DoctorModel) -> Doctor:
        return Doctor(m.id, m.full_name, m.specialty)

    def add(self, doctor: Doctor) -> Doctor:
        model = DoctorModel(full_name=doctor.full_name, specialty=doctor.specialty)
        self._s.add(model)
        self._s.flush()
        return self._entity(model)

    def get(self, doctor_id: int) -> Doctor | None:
        model = self._s.get(DoctorModel, doctor_id)
        return self._entity(model) if model else None

    def list(self, *, specialty: str | None, limit: int, offset: int) -> list[Doctor]:
        stmt = select(DoctorModel).order_by(DoctorModel.id).limit(limit).offset(offset)
        if specialty:
            stmt = stmt.where(DoctorModel.specialty.ilike(specialty))
        return [self._entity(m) for m in self._s.scalars(stmt)]


class SqlAppointmentRepository:
    def __init__(self, session: Session):
        self._s = session

    @staticmethod
    def _entity(m: AppointmentModel) -> Appointment:
        return Appointment(
            id=m.id,
            patient_id=m.patient_id,
            doctor_id=m.doctor_id,
            start=_to_aware_utc(m.start),
            end=_to_aware_utc(m.end),
            reason=m.reason,
            status=AppointmentStatus(m.status),
        )

    def add(self, appointment: Appointment) -> Appointment:
        model = AppointmentModel(
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            start=_to_naive_utc(appointment.start),
            end=_to_naive_utc(appointment.end),
            reason=appointment.reason,
            status=appointment.status.value,
        )
        self._s.add(model)
        self._s.flush()
        return self._entity(model)

    def get(self, appointment_id: int) -> Appointment | None:
        model = self._s.get(AppointmentModel, appointment_id)
        return self._entity(model) if model else None

    def update(self, appointment: Appointment) -> Appointment:
        model = self._s.get(AppointmentModel, appointment.id)
        model.status = appointment.status.value
        self._s.flush()
        return self._entity(model)

    def list(
        self,
        *,
        doctor_id: int | None,
        patient_id: int | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
        offset: int,
    ) -> list[Appointment]:
        stmt = select(AppointmentModel).order_by(AppointmentModel.start).limit(limit).offset(offset)
        if doctor_id is not None:
            stmt = stmt.where(AppointmentModel.doctor_id == doctor_id)
        if patient_id is not None:
            stmt = stmt.where(AppointmentModel.patient_id == patient_id)
        if start is not None and end is not None:
            stmt = stmt.where(
                AppointmentModel.start >= _to_naive_utc(start),
                AppointmentModel.start < _to_naive_utc(end),
            )
        return [self._entity(m) for m in self._s.scalars(stmt)]

    def find_scheduled_overlapping(
        self, *, start: datetime, end: datetime, doctor_id: int | None, patient_id: int | None
    ) -> list[Appointment]:
        owner = []
        if doctor_id is not None:
            owner.append(AppointmentModel.doctor_id == doctor_id)
        if patient_id is not None:
            owner.append(AppointmentModel.patient_id == patient_id)
        stmt = select(AppointmentModel).where(
            AppointmentModel.status == AppointmentStatus.SCHEDULED.value,
            or_(*owner),
            and_(
                AppointmentModel.start < _to_naive_utc(end),
                AppointmentModel.end > _to_naive_utc(start),
            ),
        )
        return [self._entity(m) for m in self._s.scalars(stmt)]
