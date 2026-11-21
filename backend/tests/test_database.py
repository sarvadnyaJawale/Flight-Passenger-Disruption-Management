import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models  # noqa: F401


def test_all_tables_created():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    expected = [
        "flights", "flight_inventory", "bookings", "connection_rules",
        "loyalty", "disruptions", "disruption_passengers",
        "recovery_options", "recovery_costs", "audit_log",
    ]
    for table in expected:
        assert table in tables, f"Missing table: {table}"


def test_session_works():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    from app.models.disruption import Disruption
    from datetime import date
    d = Disruption(
        flight_number="G9001",
        flight_date=date(2026, 11, 22),
        disruption_type="cancellation",
        reason="technical",
    )
    session.add(d)
    session.commit()
    result = session.query(Disruption).first()
    assert result.flight_number == "G9001"
    assert result.disruption_type == "cancellation"
    session.close()
