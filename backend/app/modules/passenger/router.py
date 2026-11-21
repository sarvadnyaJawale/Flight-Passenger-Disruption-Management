from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.passenger.schemas import PassengerResponse
from app.modules.passenger.service import get_disruption_passengers, search_passengers

router = APIRouter(prefix="/api", tags=["passengers"])


@router.get(
    "/disruptions/{disruption_id}/passengers",
    response_model=list[PassengerResponse],
)
def list_passengers(disruption_id: int, db: Session = Depends(get_db)):
    passengers = get_disruption_passengers(db, disruption_id)
    return [_to_response(p) for p in passengers]


@router.get("/passengers/search", response_model=list[PassengerResponse])
def search(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    passengers = search_passengers(db, q)
    return [_to_response(p) for p in passengers]


def _to_response(p) -> dict:
    return {
        "id": p.id,
        "disruption_id": p.disruption_id,
        "pnr": p.pnr,
        "passenger_name": p.passenger_name,
        "pax_type": p.pax_type,
        "is_connecting": bool(p.is_connecting),
        "is_misconnect": bool(p.is_misconnect),
        "connecting_flight": p.connecting_flight,
        "priority_score": p.priority_score,
        "loyalty_tier": p.loyalty_tier,
        "total_fare": float(p.total_fare or 0),
        "original_segment": p.original_segment,
        "recovery_status": p.recovery_status,
        "recovery_flight": p.recovery_flight,
        "notified_at": str(p.notified_at) if p.notified_at else None,
        "recovered_at": str(p.recovered_at) if p.recovered_at else None,
        "email": p.email,
        "phone": p.phone,
    }
