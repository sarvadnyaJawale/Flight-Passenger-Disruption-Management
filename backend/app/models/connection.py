from sqlalchemy import Column, Integer, String

from app.database import Base


class ConnectionRule(Base):
    __tablename__ = "connection_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ond_code = Column(String, unique=True, nullable=False)
    origin = Column(String(3), nullable=False)
    hub = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    min_conn_time_mins = Column(Integer, nullable=False)
    max_conn_time_mins = Column(Integer, nullable=False)
    status = Column(String, default="ACT")
