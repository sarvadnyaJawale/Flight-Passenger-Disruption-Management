from sqlalchemy import Boolean, Column, Integer, String

from app.database import Base


class LoyaltyMember(Base):
    __tablename__ = "loyalty"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loyalty_id = Column(String, index=True, nullable=False)
    pax_type = Column(String)
    pax_name = Column(String)
    family_or_ind = Column(String)
    head_of_family = Column(Boolean, default=False)
    tier = Column(String, default="Basic")
    available_points = Column(Integer, default=0)
