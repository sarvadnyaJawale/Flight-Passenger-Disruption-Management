from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.disruption import Disruption, DisruptionPassenger
from app.models.flight import Flight
from app.models.recovery import RecoveryCost

HOTEL_COST_AED = 350.0
MEAL_COST_AED = 50.0
COMPENSATION_BASE_AED = 250.0
CONNECTING_BONUS_AED = 100.0
LOYALTY_BONUS_AED = 50.0
LOYALTY_BONUS_TIERS = {"Gold", "Platinum"}


def calculate_disruption_costs(db: Session, disruption_id: int) -> int:
    existing = db.query(RecoveryCost).filter(
        RecoveryCost.disruption_id == disruption_id,
        RecoveryCost.cost_type.in_(["hotel", "meal", "compensation"]),
    ).count()
    if existing > 0:
        return existing

    passengers = (
        db.query(DisruptionPassenger)
        .filter(DisruptionPassenger.disruption_id == disruption_id)
        .all()
    )
    if not passengers:
        return 0

    count = 0
    for pax in passengers:
        db.add(RecoveryCost(
            disruption_id=disruption_id,
            pnr=pax.pnr,
            cost_type="hotel",
            amount=HOTEL_COST_AED,
        ))
        count += 1

        db.add(RecoveryCost(
            disruption_id=disruption_id,
            pnr=pax.pnr,
            cost_type="meal",
            amount=MEAL_COST_AED,
        ))
        count += 1

        comp = COMPENSATION_BASE_AED
        if pax.is_connecting:
            comp += CONNECTING_BONUS_AED
        if pax.loyalty_tier in LOYALTY_BONUS_TIERS:
            comp += LOYALTY_BONUS_AED
        db.add(RecoveryCost(
            disruption_id=disruption_id,
            pnr=pax.pnr,
            cost_type="compensation",
            amount=comp,
        ))
        count += 1

    db.commit()
    return count


EU261_BASE_COMPENSATION_AED = 1000.0
EU261_CONNECTING_MULTIPLIER = 1.5


def calculate_do_nothing_baseline(db: Session, disruption_id: int) -> dict:
    passengers = (
        db.query(DisruptionPassenger)
        .filter(DisruptionPassenger.disruption_id == disruption_id)
        .all()
    )
    if not passengers:
        return {
            "stranded_pax": 0, "eu261_compensation": 0,
            "hotel_cost": 0, "meal_cost": 0, "total_liability": 0,
        }

    pax_count = len(passengers)
    eu261 = 0.0
    for pax in passengers:
        base = EU261_BASE_COMPENSATION_AED
        if pax.is_connecting:
            base *= EU261_CONNECTING_MULTIPLIER
        eu261 += base

    hotel = pax_count * HOTEL_COST_AED
    meal = pax_count * MEAL_COST_AED

    return {
        "stranded_pax": pax_count,
        "eu261_compensation": eu261,
        "hotel_cost": hotel,
        "meal_cost": meal,
        "total_liability": eu261 + hotel + meal,
    }


def calculate_cascade_impact(db: Session, flight_number: str) -> dict:
    cancelled = db.query(Flight).filter(Flight.flight_number == flight_number).first()
    if not cancelled:
        return {"cancelled_flight": flight_number, "route": None, "downstream_flights": []}

    dest = cancelled.destination
    downstream_flights = (
        db.query(Flight)
        .filter(
            Flight.origin == dest,
            Flight.flight_number != flight_number,
        )
        .all()
    )

    seen = set()
    downstream = []
    for f in downstream_flights:
        if f.flight_number in seen:
            continue
        seen.add(f.flight_number)
        downstream.append({
            "flight_number": f.flight_number,
            "origin": f.origin,
            "destination": f.destination,
            "departure_time": f.dep_time_local,
            "arrival_time": f.arr_time_local,
        })

    downstream.sort(key=lambda f: f["departure_time"])

    return {
        "cancelled_flight": flight_number,
        "route": f"{cancelled.origin}-{cancelled.destination}",
        "downstream_flights": downstream,
    }


def rank_recovery_strategies(alternatives: list[dict]) -> dict:
    if not alternatives:
        return {"cheapest": [], "fastest": [], "best_experience": []}

    cheapest = sorted(alternatives, key=lambda a: a.get("fare_difference", 0))
    fastest = sorted(alternatives, key=lambda a: a.get("departure_time", ""))
    best_experience = sorted(alternatives, key=lambda a: -(a.get("available_seats", 0)))

    return {
        "cheapest": cheapest,
        "fastest": fastest,
        "best_experience": best_experience,
    }


def get_cost_breakdown(db: Session, disruption_id: int) -> dict:
    rows = (
        db.query(RecoveryCost.cost_type, func.sum(RecoveryCost.amount))
        .filter(RecoveryCost.disruption_id == disruption_id)
        .group_by(RecoveryCost.cost_type)
        .all()
    )
    breakdown = {}
    total = 0.0
    for cost_type, amount in rows:
        val = float(amount)
        breakdown[cost_type] = val
        total += val
    breakdown["total"] = total
    return breakdown
