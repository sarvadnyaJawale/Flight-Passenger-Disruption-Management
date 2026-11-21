from sqlalchemy import Column, Date, Integer, String

from app.database import Base


class Flight(Base):
    __tablename__ = "flights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flight_number = Column(String, index=True, nullable=False)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    dep_time_local = Column(String, nullable=False)
    arr_time_local = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    schedule_start = Column(Date, nullable=False)
    schedule_end = Column(Date, nullable=False)


class FlightInventory(Base):
    __tablename__ = "flight_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flight_number = Column(String, index=True, nullable=False)
    departure_datetime_local = Column(String)
    departure_datetime_zulu = Column(String)
    aircraft_model = Column(String)
    adult_capacity = Column(Integer, default=0)
    booking_class = Column(String)
    allocated_seats = Column(Integer, default=0)
    available_seats = Column(Integer, default=0)
