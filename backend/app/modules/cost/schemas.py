from pydantic import BaseModel


class CostBreakdownResponse(BaseModel):
    hotel: float = 0
    meal: float = 0
    compensation: float = 0
    rebooking: float = 0
    refund: float = 0
    total: float = 0
