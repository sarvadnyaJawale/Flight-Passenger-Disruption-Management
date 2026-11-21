from pydantic import BaseModel


class RecoveryOptionResponse(BaseModel):
    id: int
    flight_number: str
    origin: str | None
    destination: str | None
    departure_time: str | None
    arrival_time: str | None
    available_seats: int
    fare_difference: float
    rank: int
    status: str

    model_config = {"from_attributes": True}


class RecoveryInfoResponse(BaseModel):
    disruption_type: str
    flight_number: str
    flight_date: str
    passenger_name: str | None
    pnr: str
    original_segment: str | None
    recovery_status: str
    options: list[RecoveryOptionResponse]


class AcceptRequest(BaseModel):
    option_id: int | None = None
    action: str = "accept"
