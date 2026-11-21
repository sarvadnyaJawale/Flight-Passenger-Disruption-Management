import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.booking import Booking
from app.models.disruption import Disruption, DisruptionPassenger
from app.models.flight import Flight
from app.models.loyalty import LoyaltyMember


def _compute_priority(is_connecting: bool, loyalty_tier: str | None, fare: float) -> int:
    score = 0
    if is_connecting:
        score += 40
    if loyalty_tier in ("Platinum", "Gold"):
        score += 30
    elif loyalty_tier:
        score += 10
    if fare > 2000:
        score += 20
    elif fare > 500:
        score += 10
    return score


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

    bookings = (
        db.query(Booking)
        .filter(
            Booking.flight_number == flight_number,
            Booking.seg_status != "CNX",
        )
        .all()
    )

    loyalty_map: dict[str, str] = {}
    for m in db.query(LoyaltyMember).all():
        if m.pax_name:
            loyalty_map[m.pax_name.strip().upper()] = m.tier

    seen_pnrs: set[str] = set()
    pax_count = 0
    for b in bookings:
        if b.pnr in seen_pnrs:
            continue
        seen_pnrs.add(b.pnr)

        full_name = f"{b.first_name or ''} {b.last_name or ''}".strip()
        is_conn = b.is_connecting == "Y"
        loyalty_tier = loyalty_map.get(full_name.upper())
        fare = float(b.total_fare or 0)

        dp = DisruptionPassenger(
            disruption_id=disruption.id,
            pnr=b.pnr,
            passenger_name=full_name,
            pax_type=b.pax_type_code,
            is_connecting=1 if is_conn else 0,
            original_segment=b.segment_code,
            total_fare=fare,
            loyalty_tier=loyalty_tier,
            priority_score=_compute_priority(is_conn, loyalty_tier, fare),
            email=b.email,
            phone=b.phone,
            recovery_status="pending",
        )
        db.add(dp)
        pax_count += 1

    disruption.affected_pax_count = pax_count

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
            "affected_pax": pax_count,
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
