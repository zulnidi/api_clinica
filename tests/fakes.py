"""Dobles de prueba que implementan los puertos en memoria (sin base de datos)."""

from dataclasses import replace
from datetime import UTC, datetime

from app.domain import rules
from app.domain.entities import Appointment, AppointmentStatus, Doctor, Patient, User


class FixedClock:
    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance_to(self, now: datetime) -> None:
        self._now = now


class InMemoryUsers:
    def __init__(self):
        self.items: dict[int, User] = {}

    def add(self, user):
        saved = replace(user, id=len(self.items) + 1)
        self.items[saved.id] = saved
        return saved

    def get_by_email(self, email):
        return next((u for u in self.items.values() if u.email == email), None)

    def get(self, user_id):
        return self.items.get(user_id)


class InMemoryPatients:
    def __init__(self):
        self.items: dict[int, Patient] = {}

    def add(self, patient):
        saved = replace(patient, id=len(self.items) + 1)
        self.items[saved.id] = saved
        return saved

    def get(self, patient_id):
        return self.items.get(patient_id)

    def get_by_document(self, document_id):
        return next((p for p in self.items.values() if p.document_id == document_id), None)

    def update(self, patient):
        self.items[patient.id] = patient
        return patient

    def list(self, *, query, limit, offset):
        found = [
            p for p in self.items.values() if not query or query.lower() in p.full_name.lower()
        ]
        return found[offset : offset + limit]


class InMemoryDoctors:
    def __init__(self):
        self.items: dict[int, Doctor] = {}

    def add(self, doctor):
        saved = replace(doctor, id=len(self.items) + 1)
        self.items[saved.id] = saved
        return saved

    def get(self, doctor_id):
        return self.items.get(doctor_id)

    def list(self, *, specialty, limit, offset):
        found = [d for d in self.items.values() if not specialty or d.specialty == specialty]
        return found[offset : offset + limit]


class InMemoryAppointments:
    def __init__(self):
        self.items: dict[int, Appointment] = {}

    def add(self, appointment):
        saved = replace(appointment, id=len(self.items) + 1)
        self.items[saved.id] = saved
        return saved

    def get(self, appointment_id):
        return self.items.get(appointment_id)

    def update(self, appointment):
        self.items[appointment.id] = appointment
        return appointment

    def list(self, *, doctor_id, patient_id, start, end, limit, offset):
        found = [
            a
            for a in self.items.values()
            if (doctor_id is None or a.doctor_id == doctor_id)
            and (patient_id is None or a.patient_id == patient_id)
            and (start is None or start <= a.start < end)
        ]
        return sorted(found, key=lambda a: a.start)[offset : offset + limit]

    def find_scheduled_overlapping(self, *, start, end, doctor_id, patient_id):
        return [
            a
            for a in self.items.values()
            if a.status == AppointmentStatus.SCHEDULED
            and (a.doctor_id == doctor_id or a.patient_id == patient_id)
            and rules.overlaps(a.start, a.end, start, end)
        ]


class FakeHasher:
    def hash(self, password):
        return f"hashed:{password}"

    def verify(self, password, hashed):
        return hashed == f"hashed:{password}"


class FakeTokens:
    def issue(self, user_id):
        return f"token-{user_id}"

    def read(self, token):
        from app.domain.errors import AuthenticationError

        if not token.startswith("token-"):
            raise AuthenticationError("Token inválido.")
        return int(token.removeprefix("token-"))


# Lunes 7 de enero de 2030, 10:00 en Bogotá (UTC-5) = 15:00 UTC
NOW = datetime(2030, 1, 7, 15, 0, tzinfo=UTC)
