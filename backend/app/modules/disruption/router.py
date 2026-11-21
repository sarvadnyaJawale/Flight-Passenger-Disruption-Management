from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.websocket import manager
from app.database import get_db
from app.modules.disruption.schemas import CreateDisruptionRequest, DisruptionResponse
from app.modules.disruption.service import (
    create_disruption,
    get_disruption,
    get_disruptions,
    get_flight_info,
)
from app.modules.passenger.service import identify_affected
from app.modules.notification.service import send_notifications
from app.modules.recovery.service import generate_alternatives_for_disruption

router = APIRouter(prefix="/api/disruptions", tags=["disruptions"])


@router.post("", response_model=DisruptionResponse)
async def create(body: CreateDisruptionRequest, db: Session = Depends(get_db)):
    disruption = create_disruption(
        db, body.flight_number, body.flight_date, body.disruption_type, body.reason
    )
    flight_info = get_flight_info(db, body.flight_number)

    identify_affected(db, disruption.id)
    generate_alternatives_for_disruption(db, disruption.id)
    notif_result = send_notifications(db, disruption.id)

    db.refresh(disruption)

    await manager.broadcast("disruption_created", {
        "id": disruption.id,
        "flight_number": disruption.flight_number,
        "flight_date": str(disruption.flight_date),
        "disruption_type": disruption.disruption_type,
        "affected_pax_count": disruption.affected_pax_count,
        "notified_count": notif_result["sent_count"],
        "flight_info": flight_info,
    })

    return _to_response(disruption)


@router.get("", response_model=list[DisruptionResponse])
def list_all(db: Session = Depends(get_db)):
    return [_to_response(d) for d in get_disruptions(db)]


@router.get("/{disruption_id}", response_model=DisruptionResponse)
def get_one(disruption_id: int, db: Session = Depends(get_db)):
    d = get_disruption(db, disruption_id)
    if not d:
        raise HTTPException(status_code=404, detail="Disruption not found")
    return _to_response(d)


def _to_response(d) -> dict:
    return {
        "id": d.id,
        "flight_number": d.flight_number,
        "flight_date": str(d.flight_date),
        "disruption_type": d.disruption_type,
        "reason": d.reason,
        "created_at": str(d.created_at) if d.created_at else None,
        "status": d.status,
        "affected_pax_count": d.affected_pax_count or 0,
        "recovered_pax_count": d.recovered_pax_count or 0,
    }
