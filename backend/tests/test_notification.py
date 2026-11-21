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
