import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.disruption import Disruption, DisruptionPassenger
from app.models.flight import Flight, FlightInventory
from app.models.recovery import RecoveryCost, RecoveryOption


def _compute_load_factor_uplift(inventory_rows: list, pax_fare: float) -> float:
    total_capacity = sum(r.adult_capacity or 0 for r in inventory_rows)
    total_available = sum(r.available_seats or 0 for r in inventory_rows)
    if total_capacity <= 0:
        return 0.0
    load_factor = (total_capacity - total_available) / total_capacity
    if load_factor >= 0.85:
        return round(pax_fare * 0.20, 2)
    if load_factor >= 0.70:
        return round(pax_fare * 0.10, 2)
    if load_factor >= 0.50:
        return round(pax_fare * 0.05, 2)
    return 0.0


def generate_alternatives_for_disruption(db: Session, disruption_id: int) -> int:
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        return 0

    passengers = (
        db.query(DisruptionPassenger)
        .filter(DisruptionPassenger.disruption_id == disruption_id)
        .order_by(DisruptionPassenger.priority_score.desc())
        .all()
    )
    if not passengers:
        return 0

    first_pax = passengers[0]
    segment = first_pax.original_segment or ""
    parts = segment.split("/")
    if len(parts) != 2:
        return 0
    origin, destination = parts[0], parts[1]

    candidate_flights = (
        db.query(Flight)
        .filter(Flight.origin == origin, Flight.destination == destination)
        .all()
    )

    alternatives = []
    seen_flights = set()
    for cf in candidate_flights:
        if cf.flight_number == disruption.flight_number:
            continue
        if cf.flight_number in seen_flights:
            continue
        seen_flights.add(cf.flight_number)

        inventory_rows = (
            db.query(FlightInventory)
            .filter(FlightInventory.flight_number == cf.flight_number)
            .all()
        )
        avail_seats = sum(row.available_seats or 0 for row in inventory_rows)
        if avail_seats <= 0:
            continue
        alternatives.append({
            "flight_number": cf.flight_number,
            "origin": origin,
            "destination": destination,
            "departure_time": cf.dep_time_local,
            "arrival_time": cf.arr_time_local,
            "available_seats": avail_seats,
            "_inventory_rows": inventory_rows,
        })

    alternatives.sort(key=lambda a: a["departure_time"])
    alternatives = alternatives[:3]

    total_seats = sum(a["available_seats"] for a in alternatives)
    seats_remaining = total_seats

    total_options = 0
    allocated_pnrs = []
    for pax in passengers:
        if seats_remaining <= 0:
            break
        pax_fare = float(pax.total_fare or 0)
        for rank, alt in enumerate(alternatives, 1):
            fare_diff = _compute_load_factor_uplift(
                alt["_inventory_rows"], pax_fare,
            )
            opt = RecoveryOption(
                disruption_id=disruption_id,
                pnr=pax.pnr,
                flight_number=alt["flight_number"],
                origin=alt["origin"],
                destination=alt["destination"],
                departure_time=alt["departure_time"],
                arrival_time=alt["arrival_time"],
                available_seats=alt["available_seats"],
                fare_difference=fare_diff,
                rank=rank,
                status="offered",
            )
            db.add(opt)
            total_options += 1
        allocated_pnrs.append(pax.pnr)
        seats_remaining -= 1

    db.add(AuditLog(
        disruption_id=disruption_id,
        action="alternatives_generated",
        details=json.dumps({
            "alternative_flights": [a["flight_number"] for a in alternatives],
            "pax_count": len(allocated_pnrs),
            "total_seats": total_seats,
            "skipped_pax": len(passengers) - len(allocated_pnrs),
        }),
        actor="system",
    ))
    db.commit()
    return total_options


def get_recovery_info(db: Session, disruption_id: int, pnr: str) -> dict | None:
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        return None

    pax = (
        db.query(DisruptionPassenger)
        .filter(
            DisruptionPassenger.disruption_id == disruption_id,
            DisruptionPassenger.pnr == pnr,
        )
        .first()
    )
    if not pax:
        return None

    options = (
        db.query(RecoveryOption)
        .filter(
            RecoveryOption.disruption_id == disruption_id,
            RecoveryOption.pnr == pnr,
            RecoveryOption.status == "offered",
        )
        .order_by(RecoveryOption.rank)
        .all()
    )

    if pax.recovery_status in ("pending", "notified"):
        pax.recovery_status = "options_viewed"
        db.commit()

    return {
        "disruption_type": disruption.disruption_type,
        "flight_number": disruption.flight_number,
        "flight_date": str(disruption.flight_date),
        "passenger_name": pax.passenger_name,
        "pnr": pax.pnr,
        "original_segment": pax.original_segment,
        "recovery_status": pax.recovery_status,
        "options": options,
    }


def accept_alternative(db: Session, disruption_id: int, pnr: str, option_id: int):
    option = (
        db.query(RecoveryOption)
        .filter(RecoveryOption.id == option_id, RecoveryOption.pnr == pnr)
        .first()
    )
    if not option:
        return None

    option.status = "accepted"

    other_options = (
        db.query(RecoveryOption)
        .filter(
            RecoveryOption.disruption_id == disruption_id,
            RecoveryOption.pnr == pnr,
            RecoveryOption.id != option_id,
        )
        .all()
    )
    for o in other_options:
        o.status = "declined"

    pax = (
        db.query(DisruptionPassenger)
        .filter(
            DisruptionPassenger.disruption_id == disruption_id,
            DisruptionPassenger.pnr == pnr,
        )
        .first()
    )
    if pax:
        pax.recovery_status = "self_served"
        pax.recovery_flight = option.flight_number
        pax.recovered_at = datetime.now(timezone.utc)

    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if disruption:
        recovered = (
            db.query(DisruptionPassenger)
            .filter(
                DisruptionPassenger.disruption_id == disruption_id,
                DisruptionPassenger.recovery_status.in_(["self_served", "manually_handled"]),
            )
            .count()
        )
        disruption.recovered_pax_count = recovered

    if float(option.fare_difference or 0) != 0:
        db.add(RecoveryCost(
            disruption_id=disruption_id,
            pnr=pnr,
            cost_type="rebooking_fare_diff",
            amount=float(option.fare_difference),
        ))

    db.add(AuditLog(
        disruption_id=disruption_id,
        pnr=pnr,
        action="alternative_accepted",
        details=json.dumps({
            "flight": option.flight_number,
            "fare_diff": float(option.fare_difference or 0),
        }),
        actor="passenger",
    ))
    db.commit()
    return option


def request_refund(db: Session, disruption_id: int, pnr: str):
    pax = (
        db.query(DisruptionPassenger)
        .filter(
            DisruptionPassenger.disruption_id == disruption_id,
            DisruptionPassenger.pnr == pnr,
        )
        .first()
    )
    if not pax:
        return None

    pax.recovery_status = "refunded"
    pax.recovered_at = datetime.now(timezone.utc)

    options = (
        db.query(RecoveryOption)
        .filter(
            RecoveryOption.disruption_id == disruption_id,
            RecoveryOption.pnr == pnr,
        )
        .all()
    )
    for o in options:
        o.status = "declined"

    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if disruption:
        recovered = (
            db.query(DisruptionPassenger)
            .filter(
                DisruptionPassenger.disruption_id == disruption_id,
                DisruptionPassenger.recovery_status.in_(
                    ["self_served", "manually_handled", "refunded"]
                ),
            )
            .count()
        )
        disruption.recovered_pax_count = recovered

    db.add(RecoveryCost(
        disruption_id=disruption_id,
        pnr=pnr,
        cost_type="refund",
        amount=float(pax.total_fare or 0),
    ))
    db.add(AuditLog(
        disruption_id=disruption_id,
        pnr=pnr,
        action="refund_requested",
        details=json.dumps({"fare": float(pax.total_fare or 0)}),
        actor="passenger",
    ))
    db.commit()
    return pax
