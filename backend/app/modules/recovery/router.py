from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.modules.recovery.schemas import AcceptRequest, RecoveryInfoResponse
from app.modules.recovery.service import (
    accept_alternative,
    get_recovery_info,
    request_refund,
)

router = APIRouter(prefix="/api/recovery", tags=["recovery"])


def _decode_token(token: str) -> dict:
    try:
        return decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired recovery link")


@router.get("/{token}", response_model=RecoveryInfoResponse)
def get_recovery(token: str, db: Session = Depends(get_db)):
    payload = _decode_token(token)
    info = get_recovery_info(db, payload["disruption_id"], payload["pnr"])
    if not info:
        raise HTTPException(status_code=404, detail="Recovery info not found")
    return info


@router.post("/{token}/accept")
def accept(token: str, body: AcceptRequest, db: Session = Depends(get_db)):
    payload = _decode_token(token)
    disruption_id = payload["disruption_id"]
    pnr = payload["pnr"]

    if body.action == "refund":
        result = request_refund(db, disruption_id, pnr)
        if not result:
            raise HTTPException(status_code=404, detail="Passenger not found")
        return {"status": "refunded", "message": "Refund request submitted"}

    if not body.option_id:
        raise HTTPException(status_code=400, detail="option_id required for accept")

    result = accept_alternative(db, disruption_id, pnr, body.option_id)
    if not result:
        raise HTTPException(status_code=404, detail="Option not found")
    return {
        "status": "accepted",
        "flight_number": result.flight_number,
        "departure_time": result.departure_time,
    }
