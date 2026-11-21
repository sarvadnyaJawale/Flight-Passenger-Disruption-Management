import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.booking import Booking
from app.models.disruption import Disruption, DisruptionPassenger
from app.models.flight import Flight, FlightInventory
from app.models.recovery import RecoveryOption
from app.modules.recovery.service import (
    accept_alternative,
    generate_alternatives_for_disruption,
    request_refund,
)


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _seed(session):
    d = Disruption(
        flight_number="G9001",
        flight_date=date(2026, 11, 22),
        disruption_type="cancellation",
    )
    session.add(d)
    session.flush()

    session.add(DisruptionPassenger(
        disruption_id=d.id,
        pnr="ABC123",
        passenger_name="Test User",
        original_segment="SHJ/JED",
        recovery_status="pending",
        total_fare=500,
    ))

    session.add(Flight(
        flight_number="G9001", origin="SHJ", destination="JED",
        dep_time_local="09:00", arr_time_local="10:50",
        frequency="MON:TUE:WED", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.add(Flight(
        flight_number="G9003", origin="SHJ", destination="JED",
        dep_time_local="13:00", arr_time_local="14:50",
        frequency="MON:TUE:WED", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))

    session.add(FlightInventory(
        flight_number="G9003",
        departure_datetime_local="2026-11-22 13:00:00",
        departure_datetime_zulu="2026-11-22 09:00:00",
        aircraft_model="A320-174", adult_capacity=174,
        booking_class="E70", allocated_seats=174, available_seats=45,
    ))
    session.commit()
    return d


def test_generate_alternatives():
    session = _make_session()
    d = _seed(session)
    count = generate_alternatives_for_disruption(session, d.id)
    assert count > 0
    options = session.query(RecoveryOption).filter(RecoveryOption.pnr == "ABC123").all()
    assert len(options) == 1
    assert options[0].flight_number == "G9003"
    session.close()


def test_accept_alternative():
    session = _make_session()
    d = _seed(session)
    generate_alternatives_for_disruption(session, d.id)
    opt = session.query(RecoveryOption).filter(RecoveryOption.pnr == "ABC123").first()
    result = accept_alternative(session, d.id, "ABC123", opt.id)
    assert result is not None
    assert result.status == "accepted"
    pax = session.query(DisruptionPassenger).filter(DisruptionPassenger.pnr == "ABC123").first()
    assert pax.recovery_status == "self_served"
    assert pax.recovery_flight == "G9003"
    session.close()


def test_request_refund():
    session = _make_session()
    d = _seed(session)
    result = request_refund(session, d.id, "ABC123")
    assert result is not None
    assert result.recovery_status == "refunded"
    session.close()


# ---------------------------------------------------------------------------
# Feature 2: Policy-driven alternative generation
# ---------------------------------------------------------------------------

def _seed_priority(session):
    """Seed a disruption with 3 passengers at different priorities and
    one alternative flight with only 2 available seats."""
    d = Disruption(
        flight_number="G9001",
        flight_date=date(2026, 11, 22),
        disruption_type="cancellation",
    )
    session.add(d)
    session.flush()

    session.add(DisruptionPassenger(
        disruption_id=d.id,
        pnr="HIGH01",
        passenger_name="VIP Passenger",
        original_segment="SHJ/JED",
        recovery_status="pending",
        total_fare=2500,
        is_connecting=1,
        is_misconnect=1,
        loyalty_tier="Gold",
        priority_score=90,
    ))
    session.add(DisruptionPassenger(
        disruption_id=d.id,
        pnr="MED01",
        passenger_name="Loyalty Passenger",
        original_segment="SHJ/JED",
        recovery_status="pending",
        total_fare=800,
        is_connecting=0,
        is_misconnect=0,
        loyalty_tier="Silver",
        priority_score=20,
    ))
    session.add(DisruptionPassenger(
        disruption_id=d.id,
        pnr="LOW01",
        passenger_name="Regular Passenger",
        original_segment="SHJ/JED",
        recovery_status="pending",
        total_fare=300,
        is_connecting=0,
        is_misconnect=0,
        priority_score=0,
    ))

    session.add(Flight(
        flight_number="G9001", origin="SHJ", destination="JED",
        dep_time_local="09:00", arr_time_local="10:50",
        frequency="MON:TUE:WED", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.add(Flight(
        flight_number="G9005", origin="SHJ", destination="JED",
        dep_time_local="14:00", arr_time_local="15:50",
        frequency="MON:TUE:WED", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.add(FlightInventory(
        flight_number="G9005",
        departure_datetime_local="2026-11-22 14:00:00",
        departure_datetime_zulu="2026-11-22 10:00:00",
        aircraft_model="A320-174", adult_capacity=174,
        booking_class="E70", allocated_seats=174, available_seats=2,
    ))
    session.commit()
    return d


def test_priority_allocation_high_priority_first():
    """When seats are scarce, highest-priority passengers get options first."""
    session = _make_session()
    d = _seed_priority(session)
    generate_alternatives_for_disruption(session, d.id)

    high_opts = session.query(RecoveryOption).filter(RecoveryOption.pnr == "HIGH01").all()
    med_opts = session.query(RecoveryOption).filter(RecoveryOption.pnr == "MED01").all()
    low_opts = session.query(RecoveryOption).filter(RecoveryOption.pnr == "LOW01").all()

    assert len(high_opts) > 0, "High-priority passenger must get options"
    assert len(med_opts) > 0, "Medium-priority passenger must get options (2 seats)"
    assert len(low_opts) == 0, "Low-priority passenger should be excluded (no seats left)"
    session.close()


def test_seat_capacity_caps_total_allocations():
    """Number of passengers receiving options must not exceed available seats."""
    session = _make_session()
    d = _seed_priority(session)
    generate_alternatives_for_disruption(session, d.id)

    pnrs_with_options = {
        r[0] for r in session.query(RecoveryOption.pnr).distinct().all()
    }
    assert len(pnrs_with_options) <= 2, (
        f"Only 2 seats available but {len(pnrs_with_options)} passengers got options"
    )
    session.close()


def test_fare_difference_reflects_load_factor():
    """Fare difference should be non-zero when alternative has high load factor."""
    session = _make_session()
    d = _seed(session)
    generate_alternatives_for_disruption(session, d.id)
    opt = session.query(RecoveryOption).filter(RecoveryOption.pnr == "ABC123").first()
    assert opt is not None
    assert float(opt.fare_difference) > 0, (
        "fare_difference should reflect load-factor uplift, not be hardcoded 0"
    )
    session.close()
