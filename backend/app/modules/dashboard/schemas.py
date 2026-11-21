from pydantic import BaseModel


class KpiResponse(BaseModel):
    affected_pax_count: int
    recovered_pax_count: int
    self_service_count: int
    refund_count: int
    self_service_rate: float
    avg_recovery_time_seconds: float | None
    total_recovery_cost: float
    pending_count: int
    notified_count: int


class FlightListItem(BaseModel):
    flight_number: str
    origin: str
    destination: str
    dep_time: str
    arr_time: str

    model_config = {"from_attributes": True}
