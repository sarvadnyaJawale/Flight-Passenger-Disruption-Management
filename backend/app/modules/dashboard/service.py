from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.disruption import Disruption, DisruptionPassenger
from app.models.flight import Flight
from app.models.recovery import RecoveryCost
from app.modules.cost.service import get_cost_breakdown


def get_kpis(db: Session, disruption_id: int | None = None) -> dict:
    q = db.query(DisruptionPassenger)
    if disruption_id:
        q = q.filter(DisruptionPassenger.disruption_id == disruption_id)

    total = q.count()
    recovered = q.filter(
        DisruptionPassenger.recovery_status.in_(["self_served", "manually_handled", "refunded"])
    ).count()
    self_served = q.filter(DisruptionPassenger.recovery_status == "self_served").count()
    refunded = q.filter(DisruptionPassenger.recovery_status == "refunded").count()
    pending = q.filter(DisruptionPassenger.recovery_status == "pending").count()
    notified = q.filter(DisruptionPassenger.recovery_status == "notified").count()

    self_service_rate = (self_served / recovered * 100) if recovered > 0 else 0.0

    avg_time = None
    recovered_pax = (
        q.filter(DisruptionPassenger.recovered_at.isnot(None))
        .all()
    )
    if recovered_pax:
        times = []
        for pax in recovered_pax:
            d = db.query(Disruption).filter(Disruption.id == pax.disruption_id).first()
            if d and d.created_at and pax.recovered_at:
                diff = (pax.recovered_at - d.created_at).total_seconds()
                times.append(diff)
        if times:
            avg_time = sum(times) / len(times)

    cost_q = db.query(func.sum(RecoveryCost.amount))
    if disruption_id:
        cost_q = cost_q.filter(RecoveryCost.disruption_id == disruption_id)
    total_cost = cost_q.scalar() or 0

    breakdown = get_cost_breakdown(db, disruption_id) if disruption_id else None

    return {
        "affected_pax_count": total,
        "recovered_pax_count": recovered,
        "self_service_count": self_served,
        "refund_count": refunded,
        "self_service_rate": round(self_service_rate, 1),
        "avg_recovery_time_seconds": round(avg_time, 1) if avg_time else None,
        "total_recovery_cost": float(total_cost),
        "cost_breakdown": breakdown,
        "pending_count": pending,
        "notified_count": notified,
    }


def get_flights(db: Session) -> list[dict]:
    flights = (
        db.query(Flight)
        .group_by(Flight.flight_number)
        .order_by(Flight.flight_number)
        .all()
    )
    seen = set()
    result = []
    for f in flights:
        if f.flight_number in seen:
            continue
        seen.add(f.flight_number)
        result.append({
            "flight_number": f.flight_number,
            "origin": f.origin,
            "destination": f.destination,
            "dep_time": f.dep_time_local,
            "arr_time": f.arr_time_local,
        })
    return result
