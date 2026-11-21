import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.disruption import Disruption, DisruptionPassenger
from app.models.recovery import RecoveryCost
from app.modules.dashboard.service import get_kpis


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_kpis():
    session = _make_session()
    now = datetime.now(timezone.utc)
    d = Disruption(
        flight_number="G9001",
        flight_date=date(2026, 11, 22),
        disruption_type="cancellation",
        created_at=now,
    )
    session.add(d)
    session.flush()

    session.add(DisruptionPassenger(
        disruption_id=d.id, pnr="A01", recovery_status="self_served",
        recovered_at=now + timedelta(minutes=5),
    ))
    session.add(DisruptionPassenger(
        disruption_id=d.id, pnr="A02", recovery_status="notified",
    ))
    session.add(DisruptionPassenger(
        disruption_id=d.id, pnr="A03", recovery_status="pending",
    ))
    session.add(RecoveryCost(
        disruption_id=d.id, pnr="A01", cost_type="rebooking_fare_diff", amount=150,
    ))
    session.commit()

    kpis = get_kpis(session, d.id)
    assert kpis["affected_pax_count"] == 3
    assert kpis["recovered_pax_count"] == 1
    assert kpis["self_service_count"] == 1
    assert kpis["self_service_rate"] == 100.0
    assert kpis["total_recovery_cost"] == 150.0
    assert kpis["pending_count"] == 1
    assert kpis["notified_count"] == 1
    session.close()
