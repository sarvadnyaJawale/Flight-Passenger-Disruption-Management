import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.booking import Booking
from app.models.disruption import DisruptionPassenger
from app.models.flight import Flight
from app.models.loyalty import LoyaltyMember
from app.modules.disruption.service import create_disruption, get_disruptions, get_disruption, _compute_priority


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _seed_flights_and_bookings(session):
    session.add(Flight(
        flight_number="G9027", origin="SHJ", destination="DOH",
        dep_time_local="21:00", arr_time_local="21:50",
        frequency="1234567", schedule_start=date(2027, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.add(Flight(
        flight_number="G9028", origin="DOH", destination="SHJ",
        dep_time_local="22:25", arr_time_local="00:30",
        frequency="1234567", schedule_start=date(2027, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.add(Booking(
        pnr="CONN01", flight_number="G9027", segment_code="SHJ/DOH",
        first_name="Ali", last_name="Khan", pax_type_code="ADT",
        total_fare=1500, is_connecting="N", seg_status="HK",
    ))
    session.add(Booking(
        pnr="CONN01", flight_number="G9028", segment_code="DOH/SHJ",
        first_name="Ali", last_name="Khan", pax_type_code="ADT",
        total_fare=1500, is_connecting="N", seg_status="HK",
    ))
    session.add(Booking(
        pnr="SOLO01", flight_number="G9027", segment_code="SHJ/DOH",
        first_name="Sara", last_name="Ahmed", pax_type_code="ADT",
        total_fare=800, is_connecting="N", seg_status="HK",
    ))
    session.add(Booking(
        pnr="CANCEL", flight_number="G9027", segment_code="SHJ/DOH",
        first_name="Cancelled", last_name="Pax", pax_type_code="ADT",
        total_fare=500, is_connecting="N", seg_status="CNX",
    ))
    session.add(LoyaltyMember(loyalty_id="LM001", pax_name="ALI KHAN", tier="Gold", available_points=50000))
    session.commit()


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


def test_passengers_linked_excludes_cancelled():
    session = _make_session()
    _seed_flights_and_bookings(session)
    d = create_disruption(session, "G9027", "2027-03-04", "cancellation", "technical")
    pax = session.query(DisruptionPassenger).filter(
        DisruptionPassenger.disruption_id == d.id
    ).all()
    pnrs = {p.pnr for p in pax}
    assert "CONN01" in pnrs
    assert "SOLO01" in pnrs
    assert "CANCEL" not in pnrs
    assert d.affected_pax_count == 2
    session.close()


def test_misconnect_detected():
    session = _make_session()
    _seed_flights_and_bookings(session)
    d = create_disruption(session, "G9027", "2027-03-04", "cancellation", "technical")
    conn_pax = session.query(DisruptionPassenger).filter(
        DisruptionPassenger.disruption_id == d.id,
        DisruptionPassenger.pnr == "CONN01",
    ).first()
    assert conn_pax.is_connecting == 1
    assert conn_pax.is_misconnect == 1
    assert conn_pax.connecting_flight == "G9028"
    session.close()


def test_solo_passenger_not_misconnect():
    session = _make_session()
    _seed_flights_and_bookings(session)
    d = create_disruption(session, "G9027", "2027-03-04", "cancellation", "technical")
    solo_pax = session.query(DisruptionPassenger).filter(
        DisruptionPassenger.disruption_id == d.id,
        DisruptionPassenger.pnr == "SOLO01",
    ).first()
    assert solo_pax.is_connecting == 0
    assert solo_pax.is_misconnect == 0
    assert solo_pax.connecting_flight is None
    session.close()


def test_priority_connecting_loyalty_higher():
    session = _make_session()
    _seed_flights_and_bookings(session)
    d = create_disruption(session, "G9027", "2027-03-04", "cancellation", "technical")
    conn_pax = session.query(DisruptionPassenger).filter(
        DisruptionPassenger.disruption_id == d.id,
        DisruptionPassenger.pnr == "CONN01",
    ).first()
    solo_pax = session.query(DisruptionPassenger).filter(
        DisruptionPassenger.disruption_id == d.id,
        DisruptionPassenger.pnr == "SOLO01",
    ).first()
    assert conn_pax.priority_score > solo_pax.priority_score
    assert conn_pax.loyalty_tier == "Gold"
    session.close()


def test_compute_priority():
    assert _compute_priority(True, "Platinum", 3000) == 90
    assert _compute_priority(False, None, 100) == 0
    assert _compute_priority(True, "Gold", 600) == 80
    assert _compute_priority(False, "Silver", 2500) == 30
