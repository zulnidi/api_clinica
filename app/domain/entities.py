from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass(frozen=True)
class User:
    id: int | None
    email: str
    password_hash: str


@dataclass(frozen=True)
class Patient:
    id: int | None
    full_name: str
    document_id: str
    email: str
    phone: str | None = None


@dataclass(frozen=True)
class Doctor:
    id: int | None
    full_name: str
    specialty: str


@dataclass(frozen=True)
class Appointment:
    id: int | None
    patient_id: int
    doctor_id: int
    start: datetime  # siempre con zona horaria (UTC)
    end: datetime
    reason: str
    status: AppointmentStatus = AppointmentStatus.SCHEDULED
