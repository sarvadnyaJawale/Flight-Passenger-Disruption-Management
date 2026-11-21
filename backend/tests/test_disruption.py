import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.flight import Flight
from app.modules.disruption.service import create_disruption, get_disruptions, get_disruption


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_create_disruption():
    session = _make_session()
    session.add(Flight(
        flight_number="G9001", origin="SHJ", destination="JED",
        dep_time_local="09:00", arr_time_local="10:50",
        frequency="DAILY", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.commit()

    d = create_disruption(session, "G9001", "2026-11-22", "cancellation", "weather")
    assert d.flight_number == "G9001"
    assert d.disruption_type == "cancellation"
    session.close()


def test_get_disruptions():
    session = _make_session()
    session.add(Flight(
        flight_number="G9001", origin="SHJ", destination="JED",
        dep_time_local="09:00", arr_time_local="10:50",
        frequency="DAILY", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.commit()

    create_disruption(session, "G9001", "2026-11-22", "cancellation", "tech")
    create_disruption(session, "G9001", "2026-11-23", "delay", "weather")
    results = get_disruptions(session)
    assert len(results) == 2
    session.close()
