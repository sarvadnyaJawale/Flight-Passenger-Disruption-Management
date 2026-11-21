from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Date, Integer, Numeric, String

from app.database import Base


class Disruption(Base):
    __tablename__ = "disruptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flight_number = Column(String, nullable=False)
    flight_date = Column(Date, nullable=False)
    disruption_type = Column(String, nullable=False)
    reason = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = Column(String, default="operator")
    status = Column(String, default="active")
    affected_pax_count = Column(Integer, default=0)
    recovered_pax_count = Column(Integer, default=0)


class DisruptionPassenger(Base):
    __tablename__ = "disruption_passengers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disruption_id = Column(Integer, nullable=False)
    pnr = Column(String, nullable=False, index=True)
    passenger_name = Column(String)
    pax_type = Column(String)
    is_connecting = Column(Integer, default=0)
    is_misconnect = Column(Integer, default=0)
    connecting_flight = Column(String)
    priority_score = Column(Integer, default=0)
    loyalty_tier = Column(String)
    total_fare = Column(Numeric, default=0)
    original_segment = Column(String)
    recovery_status = Column(String, default="pending")
    recovery_flight = Column(String)
    notified_at = Column(DateTime)
    recovered_at = Column(DateTime)
    email = Column(String)
    phone = Column(String)
