import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.data_loader.loader import load_flights, load_connections, load_loyalty
from app.models import *  # noqa: F401,F403

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_load_flights():
    if not os.path.exists(os.path.join(DATA_DIR, "Flight Schedule.csv")):
        return
    session = _make_session()
    count = load_flights(session, DATA_DIR)
    assert count > 6000, f"Expected >6000 flights, got {count}"
    from app.models.flight import Flight
    shj_flights = session.query(Flight).filter(Flight.origin == "SHJ").count()
    assert shj_flights > 0, "Expected SHJ-origin flights"
    session.close()


def test_load_connections():
    if not os.path.exists(os.path.join(DATA_DIR, "Connection Time.xlsx")):
        return
    session = _make_session()
    count = load_connections(session, DATA_DIR)
    assert count > 30, f"Expected >30 connection rules, got {count}"
    from app.models.connection import ConnectionRule
    shj = session.query(ConnectionRule).filter(ConnectionRule.hub == "SHJ").count()
    assert shj > 0, "Expected SHJ hub rules"
    session.close()


def test_load_loyalty():
    if not os.path.exists(os.path.join(DATA_DIR, "Loyalty_Sample Data.xlsx")):
        return
    session = _make_session()
    count = load_loyalty(session, DATA_DIR)
    assert count > 0, "Expected loyalty records"
    session.close()
