from pydantic import BaseModel


class PassengerResponse(BaseModel):
    id: int
    disruption_id: int
    pnr: str
    passenger_name: str | None
    pax_type: str | None
    is_connecting: bool
    is_misconnect: bool
    connecting_flight: str | None
    priority_score: int
    loyalty_tier: str | None
    total_fare: float
    original_segment: str | None
    recovery_status: str
    recovery_flight: str | None
    notified_at: str | None
    recovered_at: str | None
    email: str | None
    phone: str | None

    model_config = {"from_attributes": True}
