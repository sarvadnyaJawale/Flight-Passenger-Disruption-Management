from pydantic import BaseModel


class CostBreakdown(BaseModel):
    hotel: float = 0
    meal: float = 0
    compensation: float = 0
    rebooking: float = 0
    refund: float = 0
    total: float = 0


class KpiResponse(BaseModel):
    affected_pax_count: int
    recovered_pax_count: int
    self_service_count: int
    refund_count: int
    self_service_rate: float
    avg_recovery_time_seconds: float | None
    total_recovery_cost: float
    cost_breakdown: CostBreakdown | None = None
    pending_count: int
    notified_count: int


class FlightListItem(BaseModel):
    flight_number: str
    origin: str
    destination: str
    dep_time: str
    arr_time: str

    model_config = {"from_attributes": True}
