from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.domain import rules
from app.domain.entities import Appointment, AppointmentStatus
from app.domain.errors import ConflictError, ValidationError

TZ = ZoneInfo("America/Bogota")
NOW = datetime(2030, 1, 7, 15, 0, tzinfo=UTC)  # lunes 10:00 Bogotá


def local(day, hour, minute=0):
    return datetime(2030, 1, day, hour, minute, tzinfo=TZ)


class TestValidateStart:
    def test_acepta_un_horario_valido(self):
        rules.validate_start(local(8, 10), NOW, TZ)  # martes 10:00

    @pytest.mark.parametrize(
        ("start", "mensaje"),
        [
            (datetime(2030, 1, 8, 10), "zona horaria"),
            (local(7, 9), "pasado"),
            (local(8, 10, 15), "punto o y media"),
            (local(12, 10), "lunes a viernes"),  # sábado
            (local(8, 7, 30), "horario de atención"),
            (local(8, 18), "horario de atención"),
        ],
    )
    def test_rechaza_horarios_invalidos(self, start, mensaje):
        with pytest.raises(ValidationError, match=mensaje):
            rules.validate_start(start, NOW, TZ)

    def test_acepta_la_ultima_franja(self):
        rules.validate_start(local(8, 17, 30), NOW, TZ)


class TestCancellation:
    def appointment(self, start, status=AppointmentStatus.SCHEDULED):
        return Appointment(1, 1, 1, start, start + rules.SLOT, "control", status)

    def test_permite_con_anticipacion(self):
        rules.validate_cancellation(self.appointment(local(8, 10)), NOW)

    def test_rechaza_con_menos_de_dos_horas(self):
        with pytest.raises(ConflictError, match="2 horas"):
            rules.validate_cancellation(self.appointment(local(7, 11)), NOW)

    def test_rechaza_si_no_esta_programada(self):
        with pytest.raises(ConflictError, match="programadas"):
            rules.validate_cancellation(
                self.appointment(local(8, 10), AppointmentStatus.CANCELLED), NOW
            )


def test_overlaps_usa_intervalos_semiabiertos():
    a, b, c = local(8, 10), local(8, 10, 30), local(8, 11)
    assert rules.overlaps(a, b, a, b)
    assert not rules.overlaps(a, b, b, c)  # una termina cuando la otra empieza


def test_daily_slots():
    slots = rules.daily_slots(date(2030, 1, 8), TZ)
    assert len(slots) == 20
    assert slots[0].hour == 8 and slots[-1].hour == 17 and slots[-1].minute == 30
    assert rules.daily_slots(date(2030, 1, 12), TZ) == []  # sábado
