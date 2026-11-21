import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disruption_id = Column(Integer)
    pnr = Column(String)
    action = Column(String, nullable=False)
    details = Column(Text)
    actor = Column(String, default="system")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def set_details(self, data: dict):
        self.details = json.dumps(data)
