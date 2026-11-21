from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.cost.schemas import BaselineResponse, CostBreakdownResponse
from app.modules.cost.service import calculate_cascade_impact, calculate_disruption_costs, calculate_do_nothing_baseline, get_cost_breakdown, rank_recovery_strategies

router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.post("/{disruption_id}/calculate")
def calculate_costs(disruption_id: int, db: Session = Depends(get_db)):
    count = calculate_disruption_costs(db, disruption_id)
    return {"calculated_records": count}


@router.get("/{disruption_id}", response_model=CostBreakdownResponse)
def get_costs(disruption_id: int, db: Session = Depends(get_db)):
    breakdown = get_cost_breakdown(db, disruption_id)
    return CostBreakdownResponse(**breakdown)


@router.get("/{disruption_id}/baseline", response_model=BaselineResponse)
def get_baseline(disruption_id: int, db: Session = Depends(get_db)):
    baseline = calculate_do_nothing_baseline(db, disruption_id)
    return BaselineResponse(**baseline)


@router.get("/{disruption_id}/strategies")
def get_strategies(disruption_id: int, db: Session = Depends(get_db)):
    from app.models.recovery import RecoveryOption
    options = (
        db.query(RecoveryOption)
        .filter(RecoveryOption.disruption_id == disruption_id)
        .all()
    )
    seen = {}
    for o in options:
        if o.flight_number not in seen:
            seen[o.flight_number] = {
                "flight_number": o.flight_number,
                "origin": o.origin,
                "destination": o.destination,
                "departure_time": o.departure_time,
                "arrival_time": o.arrival_time,
                "available_seats": o.available_seats or 0,
                "fare_difference": float(o.fare_difference or 0),
            }
    alternatives = list(seen.values())
    return rank_recovery_strategies(alternatives)


@router.get("/{disruption_id}/cascade")
def get_cascade(disruption_id: int, db: Session = Depends(get_db)):
    from app.models.disruption import Disruption
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        return {"cancelled_flight": None, "route": None, "downstream_flights": []}
    return calculate_cascade_impact(db, disruption.flight_number)
