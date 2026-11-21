import json

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.booking import Booking
from app.models.connection import ConnectionRule
from app.models.disruption import Disruption, DisruptionPassenger
from app.models.loyalty import LoyaltyMember


def _score_priority(
    pax_type: str | None,
    is_connecting: bool,
    is_misconnect: bool,
    loyalty_tier: str | None,
    head_of_family: bool,
    total_fare: float,
) -> int:
    score = 0
    tier = (loyalty_tier or "").lower()
    if tier == "gold":
        score += 5
    elif tier == "silver":
        score += 3
    elif tier == "basic":
        score += 1
    if is_misconnect:
        score += 5
    elif is_connecting:
        score += 2
    if head_of_family:
        score += 2
    ptype = (pax_type or "").upper()
    if ptype in ("CHD", "CH", "CHILD"):
        score += 3
    if total_fare > 1500:
        score += 2
    return score


def identify_affected(db: Session, disruption_id: int) -> list[DisruptionPassenger]:
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        return []

    bookings = (
        db.query(Booking)
        .filter(
            Booking.flight_number == disruption.flight_number,
            Booking.seg_status != "CNX",
        )
        .all()
    )

    loyalty_map = {}
    for member in db.query(LoyaltyMember).all():
        name_key = (member.pax_name or "").lower().strip()
        loyalty_map[name_key] = member

    seen_pnr_names = set()
    passengers = []

    for bk in bookings:
        pnr_name_key = f"{bk.pnr}_{bk.first_name}_{bk.last_name}"
        if pnr_name_key in seen_pnr_names:
            continue
        seen_pnr_names.add(pnr_name_key)

        is_connecting = bk.is_connecting == "Y"
        connecting_flight = None
        is_misconnect = False

        if is_connecting:
            other_segments = (
                db.query(Booking)
                .filter(
                    Booking.pnr == bk.pnr,
                    Booking.flight_number != disruption.flight_number,
                    Booking.seg_status != "CNX",
                )
                .all()
            )
            if other_segments:
                connecting_flight = other_segments[0].flight_number
                is_misconnect = True

        full_name = f"{bk.first_name or ''} {bk.last_name or ''}".strip()
        name_key = full_name.lower()
        loyalty = loyalty_map.get(name_key)
        loyalty_tier = loyalty.tier if loyalty else None
        head_of_family = loyalty.head_of_family if loyalty else False

        priority = _score_priority(
            pax_type=bk.pax_type_code,
            is_connecting=is_connecting,
            is_misconnect=is_misconnect,
            loyalty_tier=loyalty_tier,
            head_of_family=head_of_family,
            total_fare=float(bk.total_fare or 0),
        )

        dp = DisruptionPassenger(
            disruption_id=disruption_id,
            pnr=bk.pnr,
            passenger_name=full_name,
            pax_type=bk.pax_type_code,
            is_connecting=1 if is_connecting else 0,
            is_misconnect=1 if is_misconnect else 0,
            connecting_flight=connecting_flight,
            priority_score=priority,
            loyalty_tier=loyalty_tier,
            total_fare=float(bk.total_fare or 0),
            original_segment=bk.segment_code,
            recovery_status="pending",
            email=bk.email,
            phone=bk.phone,
        )
        db.add(dp)
        passengers.append(dp)

    db.flush()

    disruption.affected_pax_count = len(passengers)
    db.add(AuditLog(
        disruption_id=disruption_id,
        action="pax_identified",
        details=json.dumps({"count": len(passengers)}),
        actor="system",
    ))
    db.commit()
    return passengers


def get_disruption_passengers(
    db: Session, disruption_id: int
) -> list[DisruptionPassenger]:
    return (
        db.query(DisruptionPassenger)
        .filter(DisruptionPassenger.disruption_id == disruption_id)
        .order_by(DisruptionPassenger.priority_score.desc())
        .all()
    )


def search_passengers(db: Session, query: str) -> list[DisruptionPassenger]:
    q = query.strip()
    if len(q) == 6 and q.isalnum():
        return (
            db.query(DisruptionPassenger)
            .filter(DisruptionPassenger.pnr == q.upper())
            .all()
        )
    return (
        db.query(DisruptionPassenger)
        .filter(DisruptionPassenger.passenger_name.ilike(f"%{q}%"))
        .limit(50)
        .all()
    )
