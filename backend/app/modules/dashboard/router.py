from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.dashboard.schemas import FlightListItem, KpiResponse
from app.modules.dashboard.service import get_flights, get_kpis

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=KpiResponse)
def kpis(disruption_id: int | None = Query(None), db: Session = Depends(get_db)):
    return get_kpis(db, disruption_id)


@router.get("/flights", response_model=list[FlightListItem])
def flights(db: Session = Depends(get_db)):
    return get_flights(db)
