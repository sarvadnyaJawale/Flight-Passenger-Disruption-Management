from sqlalchemy import Column, Integer, Numeric, String

from app.database import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pnr = Column(String, index=True, nullable=False)
    booking_timestamp = Column(String)
    sales_channel = Column(String)
    res_status = Column(String)
    is_lms_member = Column(String)
    pax_type_code = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    flight_number = Column(String, index=True, nullable=False)
    departure_zulu = Column(String)
    segment_code = Column(String, nullable=False)
    flight_status = Column(String)
    seg_status = Column(String)
    booking_code = Column(String)
    pax_status = Column(String)
    total_fare = Column(Numeric, default=0)
    total_surcharges = Column(Numeric, default=0)
    total_taxes = Column(Numeric, default=0)
    baggage_weight = Column(String)
    meals = Column(String)
    seat_code = Column(String)
    is_connecting = Column(String, default="N")
    email = Column(String)
    phone = Column(String)
