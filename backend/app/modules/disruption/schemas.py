from pydantic import BaseModel


class CreateDisruptionRequest(BaseModel):
    flight_number: str
    flight_date: str
    disruption_type: str = "cancellation"
    reason: str = "technical"


class DisruptionResponse(BaseModel):
    id: int
    flight_number: str
    flight_date: str
    disruption_type: str
    reason: str | None
    created_at: str | None
    status: str
    affected_pax_count: int
    recovered_pax_count: int

    model_config = {"from_attributes": True}
