from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Numeric, String

from app.database import Base


class RecoveryOption(Base):
    __tablename__ = "recovery_options"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disruption_id = Column(Integer, nullable=False)
    pnr = Column(String, nullable=False, index=True)
    flight_number = Column(String, nullable=False)
    origin = Column(String(3))
    destination = Column(String(3))
    departure_time = Column(String)
    arrival_time = Column(String)
    available_seats = Column(Integer)
    fare_difference = Column(Numeric, default=0)
    rank = Column(Integer, default=1)
    status = Column(String, default="offered")


class RecoveryCost(Base):
    __tablename__ = "recovery_costs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disruption_id = Column(Integer, nullable=False)
    pnr = Column(String, nullable=False)
    cost_type = Column(String, nullable=False)
    amount = Column(Numeric, nullable=False)
    currency = Column(String, default="AED")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
