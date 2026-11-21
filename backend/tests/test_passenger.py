import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.booking import Booking
from app.models.disruption import Disruption
from app.modules.passenger.service import identify_affected, _score_priority


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_score_priority_misconnect_gold():
    score = _score_priority(
        pax_type="ADT",
        is_connecting=True,
        is_misconnect=True,
        loyalty_tier="Gold",
        head_of_family=True,
        total_fare=2000.0,
    )
    assert score == 5 + 5 + 2 + 2  # gold + misconnect + family + high fare = 14


def test_score_priority_basic_direct():
    score = _score_priority(
        pax_type="ADT",
        is_connecting=False,
        is_misconnect=False,
        loyalty_tier="Basic",
        head_of_family=False,
        total_fare=500.0,
    )
    assert score == 1


def test_identify_affected():
    session = _make_session()
    d = Disruption(
        flight_number="G9001",
        flight_date=date(2026, 11, 22),
        disruption_type="cancellation",
        reason="technical",
    )
    session.add(d)
    session.flush()

    session.add(Booking(
        pnr="TEST01",
        flight_number="G9001",
        first_name="John",
        last_name="Doe",
        pax_type_code="ADT",
        segment_code="SHJ/JED",
        seg_status="HK",
        is_connecting="N",
        email="john@example.com",
        phone="+971-50-123-4567",
        total_fare=800,
    ))
    session.commit()

    passengers = identify_affected(session, d.id)
    assert len(passengers) == 1
    assert passengers[0].pnr == "TEST01"
    assert passengers[0].passenger_name == "John Doe"
    session.close()
