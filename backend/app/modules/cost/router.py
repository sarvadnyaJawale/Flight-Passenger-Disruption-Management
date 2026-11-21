from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.cost.schemas import BaselineResponse, CostBreakdownResponse
from app.modules.cost.service import calculate_disruption_costs, calculate_do_nothing_baseline, get_cost_breakdown

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
