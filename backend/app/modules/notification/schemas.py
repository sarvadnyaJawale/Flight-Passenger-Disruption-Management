from pydantic import BaseModel


class NotificationStatusResponse(BaseModel):
    disruption_id: int
    total_passengers: int
    notified: int
    pending: int


class SendNotificationsResponse(BaseModel):
    disruption_id: int
    sent_count: int
    deep_links: list[dict]
