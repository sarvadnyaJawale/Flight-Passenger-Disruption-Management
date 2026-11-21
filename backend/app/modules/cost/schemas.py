from pydantic import BaseModel


class CostBreakdownResponse(BaseModel):
    hotel: float = 0
    meal: float = 0
    compensation: float = 0
    rebooking: float = 0
    refund: float = 0
    total: float = 0


class BaselineResponse(BaseModel):
    stranded_pax: int = 0
    eu261_compensation: float = 0
    hotel_cost: float = 0
    meal_cost: float = 0
    total_liability: float = 0
