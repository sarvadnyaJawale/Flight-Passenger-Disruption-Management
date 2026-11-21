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
