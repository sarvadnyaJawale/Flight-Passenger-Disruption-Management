from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.disruption import DisruptionPassenger
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
