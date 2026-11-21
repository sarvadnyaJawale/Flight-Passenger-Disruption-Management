import os
from datetime import date

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_cost.db")

from app.database import Base, engine, SessionLocal
from app.models.disruption import Disruption, DisruptionPassenger
from app.models.recovery import RecoveryCost
from app.modules.cost.service import calculate_disruption_costs, get_cost_breakdown


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _seed_disruption(db):
    d = Disruption(
        flight_number="G9027",
        flight_date=date(2024, 3, 15),
        disruption_type="cancellation",
        reason="technical",
        affected_pax_count=3,
    )
    db.add(d)
    db.flush()

    db.add(DisruptionPassenger(
        disruption_id=d.id, pnr="ABC123", passenger_name="Ali Khan",
        is_connecting=0, loyalty_tier="Gold", total_fare=450,
        original_segment="SHJ/DOH", recovery_status="notified",
    ))
    db.add(DisruptionPassenger(
        disruption_id=d.id, pnr="DEF456", passenger_name="Sara Ahmed",
        is_connecting=1, is_misconnect=1, loyalty_tier="Blue", total_fare=320,
        original_segment="SHJ/DOH", recovery_status="notified",
    ))
    db.add(DisruptionPassenger(
        disruption_id=d.id, pnr="GHI789", passenger_name="John Doe",
        is_connecting=0, loyalty_tier="Platinum", total_fare=600,
        original_segment="SHJ/DOH", recovery_status="notified",
    ))
    db.commit()
    return d


def test_calculate_costs_creates_records():
    db = SessionLocal()
    d = _seed_disruption(db)

    count = calculate_disruption_costs(db, d.id)

    assert count > 0
    costs = db.query(RecoveryCost).filter(RecoveryCost.disruption_id == d.id).all()
    cost_types = {c.cost_type for c in costs}
    assert "hotel" in cost_types
    assert "meal" in cost_types
    assert "compensation" in cost_types
    db.close()


def test_cost_amounts():
    db = SessionLocal()
    d_id = db.query(Disruption).first().id
    costs = db.query(RecoveryCost).filter(RecoveryCost.disruption_id == d_id).all()

    hotel_costs = [c for c in costs if c.cost_type == "hotel"]
    meal_costs = [c for c in costs if c.cost_type == "meal"]
    comp_costs = [c for c in costs if c.cost_type == "compensation"]

    for h in hotel_costs:
        assert float(h.amount) == 350.0

    for m in meal_costs:
        assert float(m.amount) == 50.0

    assert len(comp_costs) == 3
    comp_by_pnr = {c.pnr: float(c.amount) for c in comp_costs}
    assert comp_by_pnr["ABC123"] == 300  # base 250 + Gold bonus 50
    assert comp_by_pnr["DEF456"] == 350  # base 250 + connecting 100
    assert comp_by_pnr["GHI789"] == 300  # base 250 + Platinum bonus 50
    db.close()


def test_get_cost_breakdown():
    db = SessionLocal()
    d_id = db.query(Disruption).first().id

    breakdown = get_cost_breakdown(db, d_id)

    assert breakdown["hotel"] > 0
    assert breakdown["meal"] > 0
    assert breakdown["compensation"] > 0
    assert breakdown["total"] == breakdown["hotel"] + breakdown["meal"] + breakdown["compensation"] + breakdown.get("rebooking", 0) + breakdown.get("refund", 0)
    db.close()


def test_do_nothing_baseline():
    from app.modules.cost.service import calculate_do_nothing_baseline

    db = SessionLocal()
    d_id = db.query(Disruption).first().id

    baseline = calculate_do_nothing_baseline(db, d_id)

    assert baseline["stranded_pax"] == 3
    assert baseline["eu261_compensation"] > 0
    assert baseline["hotel_cost"] == 3 * 350
    assert baseline["meal_cost"] == 3 * 50
    assert baseline["total_liability"] > 0
    assert baseline["total_liability"] > baseline["eu261_compensation"]
    db.close()


def test_baseline_vs_recovery_savings():
    from app.modules.cost.service import calculate_do_nothing_baseline

    db = SessionLocal()
    d_id = db.query(Disruption).first().id

    baseline = calculate_do_nothing_baseline(db, d_id)
    recovery = get_cost_breakdown(db, d_id)

    assert baseline["total_liability"] > recovery["total"]
    savings = baseline["total_liability"] - recovery["total"]
    assert savings > 0
    db.close()


def test_cascade_impact():
    from app.modules.cost.service import calculate_cascade_impact

    db = SessionLocal()
    from app.models.flight import Flight
    db.add(Flight(flight_number="G9027", origin="SHJ", destination="DOH",
                  dep_time_local="08:00", arr_time_local="09:00",
                  frequency="daily", schedule_start=date(2024, 1, 1), schedule_end=date(2024, 12, 31)))
    db.add(Flight(flight_number="G9028", origin="DOH", destination="SHJ",
                  dep_time_local="11:00", arr_time_local="12:00",
                  frequency="daily", schedule_start=date(2024, 1, 1), schedule_end=date(2024, 12, 31)))
    db.add(Flight(flight_number="G9029", origin="DOH", destination="KWI",
                  dep_time_local="14:00", arr_time_local="15:30",
                  frequency="daily", schedule_start=date(2024, 1, 1), schedule_end=date(2024, 12, 31)))
    db.add(Flight(flight_number="G9050", origin="SHJ", destination="BAH",
                  dep_time_local="10:00", arr_time_local="11:00",
                  frequency="daily", schedule_start=date(2024, 1, 1), schedule_end=date(2024, 12, 31)))
    db.commit()

    cascade = calculate_cascade_impact(db, "G9027")

    assert cascade["cancelled_flight"] == "G9027"
    assert cascade["route"] == "SHJ-DOH"
    assert len(cascade["downstream_flights"]) >= 2
    flight_numbers = [f["flight_number"] for f in cascade["downstream_flights"]]
    assert "G9028" in flight_numbers  # DOH→SHJ departs from DOH
    assert "G9029" in flight_numbers  # DOH→KWI departs from DOH
    assert "G9050" not in flight_numbers  # SHJ→BAH, doesn't depart from DOH
    db.close()


def test_rank_recovery_strategies():
    from app.modules.cost.service import rank_recovery_strategies

    alternatives = [
        {"flight_number": "G9101", "departure_time": "14:00", "arrival_time": "15:30", "available_seats": 50, "fare_difference": 120},
        {"flight_number": "G9102", "departure_time": "09:00", "arrival_time": "10:30", "available_seats": 10, "fare_difference": 30},
        {"flight_number": "G9103", "departure_time": "11:00", "arrival_time": "12:30", "available_seats": 180, "fare_difference": 200},
    ]

    strategies = rank_recovery_strategies(alternatives)

    assert "cheapest" in strategies
    assert "fastest" in strategies
    assert "best_experience" in strategies

    assert strategies["cheapest"][0]["flight_number"] == "G9102"
    assert strategies["fastest"][0]["flight_number"] == "G9102"
    assert strategies["best_experience"][0]["flight_number"] == "G9103"
