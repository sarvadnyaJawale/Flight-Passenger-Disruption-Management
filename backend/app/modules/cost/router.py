from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.cost.schemas import BaselineResponse, CostBreakdownResponse
from app.modules.cost.service import (
    calculate_cascade_impact, calculate_disruption_costs,
    calculate_do_nothing_baseline, calculate_flight_risk,
    get_cost_breakdown, rank_recovery_strategies, simulate_what_if,
)

router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.post("/{disruption_id}/calculate")
def calculate_costs(disruption_id: int, db: Session = Depends(get_db)):
    count = calculate_disruption_costs(db, disruption_id)
    return {"calculated_records": count}


@router.get("/{disruption_id}", response_model=CostBreakdownResponse)
def get_costs(disruption_id: int, db: Session = Depends(get_db)):
    breakdown = get_cost_breakdown(db, disruption_id)
    return CostBreakdownResponse(**breakdown)


@router.get("/{disruption_id}/baseline", response_model=BaselineResponse)
def get_baseline(disruption_id: int, db: Session = Depends(get_db)):
    baseline = calculate_do_nothing_baseline(db, disruption_id)
    return BaselineResponse(**baseline)


@router.get("/{disruption_id}/strategies")
def get_strategies(disruption_id: int, db: Session = Depends(get_db)):
    from app.models.recovery import RecoveryOption
    options = (
        db.query(RecoveryOption)
        .filter(RecoveryOption.disruption_id == disruption_id)
        .all()
    )
    seen = {}
    for o in options:
        if o.flight_number not in seen:
            seen[o.flight_number] = {
                "flight_number": o.flight_number,
                "origin": o.origin,
                "destination": o.destination,
                "departure_time": o.departure_time,
                "arrival_time": o.arrival_time,
                "available_seats": o.available_seats or 0,
                "fare_difference": float(o.fare_difference or 0),
            }
    alternatives = list(seen.values())
    return rank_recovery_strategies(alternatives)


@router.get("/{disruption_id}/cascade")
def get_cascade(disruption_id: int, db: Session = Depends(get_db)):
    from app.models.disruption import Disruption
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        return {"cancelled_flight": None, "route": None, "downstream_flights": []}
    return calculate_cascade_impact(db, disruption.flight_number)


@router.get("/risk/{flight_number}")
def get_risk(flight_number: str, db: Session = Depends(get_db)):
    from app.models.flight import Flight, FlightInventory
    flight = db.query(Flight).filter(Flight.flight_number == flight_number).first()
    if not flight:
        return {"flight_number": flight_number, "risk_score": 0, "risk_level": "unknown"}

    inv = (
        db.query(FlightInventory)
        .filter(FlightInventory.flight_number == flight_number)
        .first()
    )
    load_factor = 0.8
    if inv and inv.adult_capacity and inv.adult_capacity > 0:
        booked = (inv.adult_capacity or 0) - (inv.available_seats or 0)
        load_factor = booked / inv.adult_capacity

    dep_hour = 12
    try:
        dep_hour = int(flight.dep_time_local.split(":")[0])
    except (ValueError, AttributeError):
        pass

    alt_count = db.query(Flight).filter(
        Flight.origin == flight.origin,
        Flight.destination == flight.destination,
        Flight.flight_number != flight_number,
    ).count()

    hub_airports = {"SHJ", "AUH", "CAI", "CMN", "RAK", "KHI"}
    is_hub = flight.origin in hub_airports or flight.destination in hub_airports

    score = calculate_flight_risk(load_factor, dep_hour, alt_count, is_hub)
    level = "high" if score >= 0.6 else ("medium" if score >= 0.35 else "low")

    return {
        "flight_number": flight_number,
        "route": f"{flight.origin}-{flight.destination}",
        "risk_score": score,
        "risk_level": level,
        "factors": {
            "load_factor": round(load_factor, 2),
            "departure_hour": dep_hour,
            "route_alternatives": alt_count,
            "connecting_hub": is_hub,
        },
    }


@router.post("/simulate")
def run_simulation(
    affected_pax: int = 150,
    delay_minutes: int = 90,
    hotel_nights: int = 1,
    include_compensation: bool = True,
):
    return simulate_what_if(affected_pax, delay_minutes, hotel_nights, include_compensation)


@router.post("/ai/analyze")
def ai_analyze(disruption_id: int, question: str = "Analyze this disruption", db: Session = Depends(get_db)):
    from app.models.disruption import Disruption
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        return {"answer": "Disruption not found", "provider": "offline"}

    breakdown = get_cost_breakdown(db, disruption_id)
    baseline = calculate_do_nothing_baseline(db, disruption_id)
    cascade = calculate_cascade_impact(db, disruption.flight_number)

    savings = baseline.get("total_liability", 0) - breakdown.get("total", 0)
    savings_pct = round(savings / baseline["total_liability"] * 100, 1) if baseline.get("total_liability") else 0

    analysis = (
        f"Disruption Analysis — {disruption.flight_number} ({disruption.disruption_type})\n\n"
        f"Affected passengers: {disruption.affected_pax_count}\n"
        f"Recovery cost: AED {breakdown.get('total', 0):,.0f} "
        f"(hotel: {breakdown.get('hotel', 0):,.0f}, meals: {breakdown.get('meal', 0):,.0f}, "
        f"compensation: {breakdown.get('compensation', 0):,.0f})\n\n"
        f"Do-nothing liability: AED {baseline.get('total_liability', 0):,.0f} "
        f"(EU261: {baseline.get('eu261_compensation', 0):,.0f})\n"
        f"Net savings from recovery: AED {savings:,.0f} ({savings_pct}% reduction)\n\n"
        f"Cascade impact: {len(cascade.get('downstream_flights', []))} downstream flights at risk\n\n"
        f"Recommendation: {'RECOVER — savings justify intervention' if savings > 0 else 'REVIEW — recovery cost exceeds liability'}\n"
        f"Evidence: deterministic calculation on real operational data"
    )

    return {"answer": analysis, "provider": "deterministic", "question": question}
