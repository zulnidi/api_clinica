"""Reglas de agenda de la clínica: funciones puras, sin base de datos ni HTTP."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.entities import Appointment, AppointmentStatus
from app.domain.errors import ConflictError, ValidationError

SLOT = timedelta(minutes=30)
OPEN_HOUR = 8
CLOSE_HOUR = 18
MIN_CANCEL_NOTICE = timedelta(hours=2)


def validate_start(start: datetime, now: datetime, tz: ZoneInfo) -> None:
    """Una cita debe ser futura, en punto o y media, en día hábil y en horario de atención."""
    if start.tzinfo is None:
        raise ValidationError("La fecha debe incluir zona horaria.")
    if start <= now:
        raise ValidationError("No se puede agendar una cita en el pasado.")
    local = start.astimezone(tz)
    if local.minute not in (0, 30) or local.second or local.microsecond:
        raise ValidationError("Las citas inician en punto o y media.")
    if local.weekday() >= 5:
        raise ValidationError("La clínica atiende de lunes a viernes.")
    if not OPEN_HOUR <= local.hour < CLOSE_HOUR:
        raise ValidationError(f"El horario de atención es de {OPEN_HOUR}:00 a {CLOSE_HOUR}:00.")


def validate_cancellation(appointment: Appointment, now: datetime) -> None:
    if appointment.status != AppointmentStatus.SCHEDULED:
        raise ConflictError("Solo se pueden cancelar citas programadas.")
    if appointment.start - now < MIN_CANCEL_NOTICE:
        raise ConflictError("Las citas se cancelan con al menos 2 horas de anticipación.")


def overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def daily_slots(day: date, tz: ZoneInfo) -> list[datetime]:
    """Todos los inicios posibles de cita de un día (vacío en fin de semana)."""
    if day.weekday() >= 5:
        return []
    cursor = datetime.combine(day, time(OPEN_HOUR), tzinfo=tz)
    closing = datetime.combine(day, time(CLOSE_HOUR), tzinfo=tz)
    slots = []
    while cursor + SLOT <= closing:
        slots.append(cursor)
        cursor += SLOT
    return slots
