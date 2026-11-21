import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.audit import AuditLog
from app.models.disruption import Disruption, DisruptionPassenger


def send_notifications(db: Session, disruption_id: int) -> dict:
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        return {"sent_count": 0, "deep_links": []}

    passengers = (
        db.query(DisruptionPassenger)
        .filter(
            DisruptionPassenger.disruption_id == disruption_id,
            DisruptionPassenger.recovery_status == "pending",
        )
        .all()
    )

    deep_links = []
    for pax in passengers:
        token = create_access_token({
            "disruption_id": disruption_id,
            "pnr": pax.pnr,
        })
        deep_link = f"{settings.FRONTEND_URL}/recover/{token}"

        print(
            f"[NOTIFICATION] To: {pax.email} | "
            f"Flight {disruption.flight_number} {disruption.disruption_type} | "
            f"Link: {deep_link}"
        )

        pax.notified_at = datetime.now(timezone.utc)
        pax.recovery_status = "notified"

        db.add(AuditLog(
            disruption_id=disruption_id,
            pnr=pax.pnr,
            action="notification_sent",
            details=json.dumps({"email": pax.email, "channel": "email"}),
            actor="system",
        ))

        deep_links.append({
            "pnr": pax.pnr,
            "name": pax.passenger_name,
            "email": pax.email,
            "deep_link": deep_link,
        })

    db.commit()

    return {
        "disruption_id": disruption_id,
        "sent_count": len(deep_links),
        "deep_links": deep_links,
    }


def get_notification_status(db: Session, disruption_id: int) -> dict:
    total = (
        db.query(DisruptionPassenger)
        .filter(DisruptionPassenger.disruption_id == disruption_id)
        .count()
    )
    notified = (
        db.query(DisruptionPassenger)
        .filter(
            DisruptionPassenger.disruption_id == disruption_id,
            DisruptionPassenger.notified_at.isnot(None),
        )
        .count()
    )
    return {
        "disruption_id": disruption_id,
        "total_passengers": total,
        "notified": notified,
        "pending": total - notified,
    }
