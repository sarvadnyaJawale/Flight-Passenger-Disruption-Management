from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.websocket import manager
from app.database import get_db
from app.modules.notification.schemas import (
    NotificationStatusResponse,
    SendNotificationsResponse,
)
from app.modules.notification.service import get_notification_status, send_notifications

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.post("/{disruption_id}/send", response_model=SendNotificationsResponse)
async def send(disruption_id: int, db: Session = Depends(get_db)):
    result = send_notifications(db, disruption_id)
    await manager.broadcast("notifications_sent", {
        "disruption_id": disruption_id,
        "count": result["sent_count"],
    })
    return result


@router.get("/{disruption_id}/status", response_model=NotificationStatusResponse)
def status(disruption_id: int, db: Session = Depends(get_db)):
    return get_notification_status(db, disruption_id)
