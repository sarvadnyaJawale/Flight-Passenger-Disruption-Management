import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.disruption import Disruption
from app.models.flight import Flight


def create_disruption(
    db: Session,
    flight_number: str,
    flight_date: str,
    disruption_type: str,
    reason: str,
) -> Disruption:
    parsed_date = datetime.strptime(flight_date, "%Y-%m-%d").date()

    disruption = Disruption(
        flight_number=flight_number,
        flight_date=parsed_date,
        disruption_type=disruption_type,
        reason=reason,
    )
    db.add(disruption)
    db.flush()

    flight = db.query(Flight).filter(Flight.flight_number == flight_number).first()
    route = f"{flight.origin}/{flight.destination}" if flight else "unknown"

    db.add(AuditLog(
        disruption_id=disruption.id,
        action="disruption_created",
        details=json.dumps({
            "flight": flight_number,
            "date": flight_date,
            "type": disruption_type,
            "reason": reason,
            "route": route,
        }),
        actor="operator",
    ))
    db.commit()
    return disruption


def get_disruptions(db: Session) -> list[Disruption]:
    return db.query(Disruption).order_by(Disruption.created_at.desc()).all()


def get_disruption(db: Session, disruption_id: int) -> Disruption | None:
    return db.query(Disruption).filter(Disruption.id == disruption_id).first()


def get_flight_info(db: Session, flight_number: str) -> dict | None:
    flight = db.query(Flight).filter(Flight.flight_number == flight_number).first()
    if not flight:
        return None
    return {
        "flight_number": flight.flight_number,
        "origin": flight.origin,
        "destination": flight.destination,
        "dep_time": flight.dep_time_local,
        "arr_time": flight.arr_time_local,
    }
