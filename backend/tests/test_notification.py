import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.disruption import Disruption, DisruptionPassenger
from app.modules.notification.service import send_notifications, get_notification_status


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_send_notifications():
    session = _make_session()
    d = Disruption(
        flight_number="G9001",
        flight_date=date(2026, 11, 22),
        disruption_type="cancellation",
    )
    session.add(d)
    session.flush()

    for i in range(3):
        session.add(DisruptionPassenger(
            disruption_id=d.id,
            pnr=f"PNR{i:03d}",
            passenger_name=f"Test {i}",
            recovery_status="pending",
            email=f"test{i}@example.com",
        ))
    session.commit()

    result = send_notifications(session, d.id)
    assert result["sent_count"] == 3
    assert len(result["deep_links"]) == 3

    for link in result["deep_links"]:
        assert "recover/" in link["deep_link"]

    status = get_notification_status(session, d.id)
    assert status["notified"] == 3
    assert status["pending"] == 0
    session.close()


# ---------------------------------------------------------------------------
# Feature 4: Auto-notification on disruption creation
# ---------------------------------------------------------------------------

from app.models.flight import Flight, FlightInventory
from app.models.booking import Booking
from app.modules.disruption.service import create_disruption
from app.modules.recovery.service import generate_alternatives_for_disruption


def test_auto_notify_after_alternatives():
    """After generating alternatives, calling send_notifications should
    transition all pending passengers to 'notified' with deep links."""
    session = _make_session()

    session.add(Flight(
        flight_number="G9001", origin="SHJ", destination="JED",
        dep_time_local="09:00", arr_time_local="10:50",
        frequency="DAILY", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.add(Flight(
        flight_number="G9003", origin="SHJ", destination="JED",
        dep_time_local="13:00", arr_time_local="14:50",
        frequency="DAILY", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.add(FlightInventory(
        flight_number="G9003",
        departure_datetime_local="2026-11-22 13:00:00",
        departure_datetime_zulu="2026-11-22 09:00:00",
        aircraft_model="A320", adult_capacity=174,
        booking_class="E70", allocated_seats=174, available_seats=50,
    ))
    for i in range(5):
        session.add(Booking(
            pnr=f"AUTO{i:02d}",
            flight_number="G9001",
            first_name=f"Auto",
            last_name=f"Pax{i}",
            segment_code="SHJ/JED",
            seg_status="HK",
            total_fare=600,
        ))
    session.commit()

    disruption = create_disruption(session, "G9001", "2026-11-22", "cancellation", "tech")
    generate_alternatives_for_disruption(session, disruption.id)

    result = send_notifications(session, disruption.id)
    assert result["sent_count"] == 5, f"Expected 5 notifications, got {result['sent_count']}"

    status = get_notification_status(session, disruption.id)
    assert status["notified"] == 5
    assert status["pending"] == 0

    for link in result["deep_links"]:
        assert "recover/" in link["deep_link"]
    session.close()
