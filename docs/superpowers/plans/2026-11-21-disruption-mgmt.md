# Flight & Passenger Disruption Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end Flight & Passenger Disruption Management platform that lets an OCC operator trigger a flight cancellation, automatically identifies affected passengers (including misconnects), generates rebooking alternatives from real inventory, sends notifications with deep links, and provides a self-service portal — all demonstrated with real Air Arabia data.

**Architecture:** Monolith with 5 feature modules (disruption, passenger, recovery, notification, dashboard). Single FastAPI backend serves a React SPA frontend. SQLite database pre-loaded with real Air Arabia operational data via ETL.

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy / Pydantic / uvicorn / PyJWT / openpyxl / xlrd · React 18 / Vite / Tailwind CSS / shadcn/ui / TanStack Query · SQLite

## Global Constraints

- Python 3.11+ required (match syntax used throughout)
- SQLite database at `backend/disruption.db` — schema is PostgreSQL-compatible
- All data files live in `data/` at repo root — never modify originals
- Booking data: load only one month's subset for demo responsiveness
- Mock contact info generated from PNR names — no real PII
- Air Arabia brand colors: red `#CE1126`, white `#FFFFFF`, dark gray `#1F2937`
- CORS: allow `http://localhost:5173` (Vite dev server)
- JWT secret: load from `RECOVERY_JWT_SECRET` env var, default `hackathon-secret-change-me`
- Every service function that mutates state must write an audit_log entry

---

### Task 1: Backend Foundation — FastAPI App, Database, All ORM Models

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/database.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/security.py`
- Create: `backend/app/core/websocket.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/flight.py`
- Create: `backend/app/models/booking.py`
- Create: `backend/app/models/connection.py`
- Create: `backend/app/models/loyalty.py`
- Create: `backend/app/models/disruption.py`
- Create: `backend/app/models/recovery.py`
- Create: `backend/app/models/audit.py`
- Test: `backend/tests/test_database.py`

**Interfaces:**
- Produces: `get_db()` generator yielding SQLAlchemy sessions — used by every router
- Produces: `Base` declarative base — used by data_loader and all models
- Produces: `ConnectionManager` class with `connect()`, `disconnect()`, `broadcast()` — used by disruption and dashboard routers
- Produces: `create_access_token(data: dict) -> str` and `decode_access_token(token: str) -> dict` — used by notification and recovery modules
- Produces: All ORM model classes — used by every service module

- [ ] **Step 1: Create `backend/requirements.txt`**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
pydantic==2.10.3
pydantic-settings==2.7.0
python-multipart==0.0.18
PyJWT==2.10.1
openpyxl==3.1.5
xlrd==2.0.1
python-dotenv==1.0.1
```

- [ ] **Step 2: Create virtual environment and install dependencies**

Run:
```bash
cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```
Expected: All packages install without errors.

- [ ] **Step 3: Create `backend/app/core/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./disruption.db"
    RECOVERY_JWT_SECRET: str = "hackathon-secret-change-me"
    RECOVERY_JWT_EXPIRE_HOURS: int = 24
    FRONTEND_URL: str = "http://localhost:5173"
    RESEND_API_KEY: str = ""
    DATA_DIR: str = "../data"

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 4: Create `backend/app/database.py`**

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 5: Create `backend/app/core/security.py`**

```python
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.RECOVERY_JWT_EXPIRE_HOURS)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.RECOVERY_JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.RECOVERY_JWT_SECRET, algorithms=["HS256"])
```

- [ ] **Step 6: Create `backend/app/core/websocket.py`**

```python
import json

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, data: dict):
        message = json.dumps({"type": event_type, "data": data})
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.active_connections.remove(connection)


manager = ConnectionManager()
```

- [ ] **Step 7: Create ORM models — `backend/app/models/flight.py`**

```python
from sqlalchemy import Column, Date, Integer, String, Time

from app.database import Base


class Flight(Base):
    __tablename__ = "flights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flight_number = Column(String, index=True, nullable=False)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    dep_time_local = Column(String, nullable=False)
    arr_time_local = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    schedule_start = Column(Date, nullable=False)
    schedule_end = Column(Date, nullable=False)


class FlightInventory(Base):
    __tablename__ = "flight_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flight_number = Column(String, index=True, nullable=False)
    departure_datetime_local = Column(String, nullable=False)
    departure_datetime_zulu = Column(String, nullable=False)
    aircraft_model = Column(String, nullable=False)
    adult_capacity = Column(Integer, nullable=False)
    booking_class = Column(String, nullable=False)
    allocated_seats = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
```

- [ ] **Step 8: Create ORM models — `backend/app/models/booking.py`**

```python
from sqlalchemy import Column, Integer, Numeric, String

from app.database import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pnr = Column(String, index=True, nullable=False)
    booking_timestamp = Column(String)
    sales_channel = Column(String)
    res_status = Column(String)
    is_lms_member = Column(String)
    pax_type_code = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    flight_number = Column(String, index=True, nullable=False)
    departure_zulu = Column(String)
    segment_code = Column(String, nullable=False)
    flight_status = Column(String)
    seg_status = Column(String)
    booking_code = Column(String)
    pax_status = Column(String)
    total_fare = Column(Numeric, default=0)
    total_surcharges = Column(Numeric, default=0)
    total_taxes = Column(Numeric, default=0)
    baggage_weight = Column(String)
    meals = Column(String)
    seat_code = Column(String)
    is_connecting = Column(String, default="N")
    email = Column(String)
    phone = Column(String)
```

- [ ] **Step 9: Create ORM models — `backend/app/models/connection.py`**

```python
from sqlalchemy import Column, Integer, String

from app.database import Base


class ConnectionRule(Base):
    __tablename__ = "connection_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ond_code = Column(String, unique=True, nullable=False)
    origin = Column(String(3), nullable=False)
    hub = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    min_conn_time_mins = Column(Integer, nullable=False)
    max_conn_time_mins = Column(Integer, nullable=False)
    status = Column(String, default="ACT")
```

- [ ] **Step 10: Create ORM models — `backend/app/models/loyalty.py`**

```python
from sqlalchemy import Boolean, Column, Integer, String

from app.database import Base


class LoyaltyMember(Base):
    __tablename__ = "loyalty"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loyalty_id = Column(String, unique=True, nullable=False)
    pax_type = Column(String)
    pax_name = Column(String)
    family_or_ind = Column(String)
    head_of_family = Column(Boolean, default=False)
    tier = Column(String, default="Basic")
    available_points = Column(Integer, default=0)
```

- [ ] **Step 11: Create ORM models — `backend/app/models/disruption.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Date, Integer, String

from app.database import Base


class Disruption(Base):
    __tablename__ = "disruptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flight_number = Column(String, nullable=False)
    flight_date = Column(Date, nullable=False)
    disruption_type = Column(String, nullable=False)
    reason = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = Column(String, default="operator")
    status = Column(String, default="active")
    affected_pax_count = Column(Integer, default=0)
    recovered_pax_count = Column(Integer, default=0)


class DisruptionPassenger(Base):
    __tablename__ = "disruption_passengers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disruption_id = Column(Integer, nullable=False)
    pnr = Column(String, nullable=False, index=True)
    passenger_name = Column(String)
    pax_type = Column(String)
    is_connecting = Column(Integer, default=0)
    is_misconnect = Column(Integer, default=0)
    connecting_flight = Column(String)
    priority_score = Column(Integer, default=0)
    loyalty_tier = Column(String)
    total_fare = Column(Numeric, default=0)
    original_segment = Column(String)
    recovery_status = Column(String, default="pending")
    recovery_flight = Column(String)
    notified_at = Column(DateTime)
    recovered_at = Column(DateTime)
    email = Column(String)
    phone = Column(String)
```

- [ ] **Step 12: Create ORM models — `backend/app/models/recovery.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Numeric, String

from app.database import Base


class RecoveryOption(Base):
    __tablename__ = "recovery_options"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disruption_id = Column(Integer, nullable=False)
    pnr = Column(String, nullable=False, index=True)
    flight_number = Column(String, nullable=False)
    origin = Column(String(3))
    destination = Column(String(3))
    departure_time = Column(String)
    arrival_time = Column(String)
    available_seats = Column(Integer)
    fare_difference = Column(Numeric, default=0)
    rank = Column(Integer, default=1)
    status = Column(String, default="offered")


class RecoveryCost(Base):
    __tablename__ = "recovery_costs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disruption_id = Column(Integer, nullable=False)
    pnr = Column(String, nullable=False)
    cost_type = Column(String, nullable=False)
    amount = Column(Numeric, nullable=False)
    currency = Column(String, default="AED")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 13: Create ORM models — `backend/app/models/audit.py`**

```python
import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disruption_id = Column(Integer)
    pnr = Column(String)
    action = Column(String, nullable=False)
    details = Column(Text)
    actor = Column(String, default="system")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def set_details(self, data: dict):
        self.details = json.dumps(data)
```

- [ ] **Step 14: Create `backend/app/models/__init__.py`**

```python
from app.models.flight import Flight, FlightInventory
from app.models.booking import Booking
from app.models.connection import ConnectionRule
from app.models.loyalty import LoyaltyMember
from app.models.disruption import Disruption, DisruptionPassenger
from app.models.recovery import RecoveryOption, RecoveryCost
from app.models.audit import AuditLog

__all__ = [
    "Flight", "FlightInventory",
    "Booking",
    "ConnectionRule",
    "LoyaltyMember",
    "Disruption", "DisruptionPassenger",
    "RecoveryOption", "RecoveryCost",
    "AuditLog",
]
```

- [ ] **Step 15: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database import Base, engine

app = FastAPI(title="Air Arabia Disruption Management", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    import app.models  # noqa: F401 — registers all models
    Base.metadata.create_all(bind=engine)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 16: Create `backend/app/__init__.py` and `backend/app/core/__init__.py`**

Both files are empty `__init__.py` files.

- [ ] **Step 17: Write test — `backend/tests/test_database.py`**

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models  # noqa: F401


def test_all_tables_created():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    expected = [
        "flights", "flight_inventory", "bookings", "connection_rules",
        "loyalty", "disruptions", "disruption_passengers",
        "recovery_options", "recovery_costs", "audit_log",
    ]
    for table in expected:
        assert table in tables, f"Missing table: {table}"


def test_session_works():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    from app.models.disruption import Disruption
    from datetime import date
    d = Disruption(
        flight_number="G9001",
        flight_date=date(2026, 11, 22),
        disruption_type="cancellation",
        reason="technical",
    )
    session.add(d)
    session.commit()
    result = session.query(Disruption).first()
    assert result.flight_number == "G9001"
    assert result.disruption_type == "cancellation"
    session.close()
```

- [ ] **Step 18: Run tests**

Run:
```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_database.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 19: Verify FastAPI starts**

Run:
```bash
cd backend && source venv/bin/activate && timeout 5 uvicorn app.main:app --host 0.0.0.0 --port 8000 || true
```
Expected: Server starts, logs `Uvicorn running on http://0.0.0.0:8000`. Verify `GET /api/health` returns `{"status": "ok"}`.

- [ ] **Step 20: Commit**

```bash
git add backend/
git commit -m "feat: backend foundation — FastAPI app, SQLAlchemy models, JWT security, WebSocket manager"
```

---

### Task 2: Data Loader — ETL from CSV/Excel/Zip into SQLite

**Files:**
- Create: `backend/app/data_loader/__init__.py`
- Create: `backend/app/data_loader/loader.py`
- Test: `backend/tests/test_loader.py`

**Interfaces:**
- Consumes: All ORM models from Task 1, `Base`, `engine`, `SessionLocal` from `app.database`
- Produces: `load_all(data_dir: str, db_url: str | None = None)` — called at startup or via CLI to populate database
- Produces: `load_flights(session, data_dir)`, `load_inventory(session, data_dir)`, `load_bookings(session, data_dir)`, `load_connections(session, data_dir)`, `load_loyalty(session, data_dir)` — individual loaders

- [ ] **Step 1: Create `backend/app/data_loader/__init__.py`**

Empty file.

- [ ] **Step 2: Create `backend/app/data_loader/loader.py`**

```python
import csv
import hashlib
import io
import os
import random
import zipfile
from datetime import datetime

import openpyxl
import xlrd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.booking import Booking
from app.models.connection import ConnectionRule
from app.models.flight import Flight, FlightInventory
from app.models.loyalty import LoyaltyMember


def load_flights(session, data_dir: str) -> int:
    path = os.path.join(data_dir, "Flight Schedule.csv")
    count = 0
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            flight = Flight(
                flight_number=row["FLIGHT_NUMBER"],
                origin=row["ORIGIN"],
                destination=row["DESTINATION"],
                dep_time_local=row["DEP_TIME_LOCAL"],
                arr_time_local=row["ARR_TIME_LOCAL"],
                frequency=row["FREQUENCY"],
                schedule_start=datetime.strptime(row["SCHEDULE_START"], "%Y-%m-%d").date(),
                schedule_end=datetime.strptime(row["SCHEDULE_END"], "%Y-%m-%d").date(),
            )
            session.add(flight)
            count += 1
    session.commit()
    return count


def load_inventory(session, data_dir: str) -> int:
    path = os.path.join(data_dir, "Flight Inventory.csv")
    count = 0
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inv = FlightInventory(
                flight_number=row["flight_number"],
                departure_datetime_local=row["departure_date_time_local"],
                departure_datetime_zulu=row["departure_date_time_zulu"],
                aircraft_model=row["aircraft_model"],
                adult_capacity=int(row["adult_capacity"]),
                booking_class=row["bc_code"],
                allocated_seats=int(row["allocated_seats"]),
                available_seats=int(row["available_seats"]),
            )
            session.add(inv)
            count += 1
            if count % 10000 == 0:
                session.flush()
    session.commit()
    return count


def _generate_mock_email(first_name: str, last_name: str, pnr: str) -> str:
    name = f"{first_name.lower().strip()}.{last_name.lower().strip()}"
    name = "".join(c for c in name if c.isalnum() or c == ".")
    if not name:
        name = pnr.lower()
    return f"{name}@example.com"


def _generate_mock_phone(pnr: str) -> str:
    h = int(hashlib.md5(pnr.encode()).hexdigest()[:8], 16)
    return f"+971-50-{h % 900 + 100}-{h % 9000 + 1000}"


def load_bookings(session, data_dir: str, target_flights: list[str] | None = None) -> int:
    zip_path = os.path.join(data_dir, "Past & Future Booking Data.zip")
    count = 0
    with zipfile.ZipFile(zip_path) as outer_zip:
        inner_zips = sorted([
            n for n in outer_zip.namelist()
            if n.endswith(".csv.zip") and "__MACOSX" not in n
        ])
        for inner_name in inner_zips:
            with outer_zip.open(inner_name) as inner_file:
                inner_bytes = inner_file.read()
            with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner_zip:
                csv_names = [n for n in inner_zip.namelist() if n.endswith(".csv")]
                for csv_name in csv_names:
                    with inner_zip.open(csv_name) as cf:
                        reader = csv.DictReader(io.TextIOWrapper(cf, "utf-8"))
                        for row in reader:
                            fn = row.get("FLIGHT_NUMBER", "")
                            if target_flights and fn not in target_flights:
                                continue
                            status = row.get("SEG_STATUS", "")
                            if status == "CNX":
                                continue
                            booking = Booking(
                                pnr=row["PNR"],
                                booking_timestamp=row.get("BOOKING_TIMESTAMP"),
                                sales_channel=row.get("SALES_CHANNEL"),
                                res_status=row.get("RES_STATUS"),
                                is_lms_member=row.get("IS_LMS_MEMBER", ""),
                                pax_type_code=row.get("PAX_TYPE_CODE"),
                                first_name=row.get("FIRST_NAME", ""),
                                last_name=row.get("LAST_NAME", ""),
                                flight_number=fn,
                                departure_zulu=row.get("EST_TIME_DEPARTURE_ZULU"),
                                segment_code=row.get("SEGMENT_CODE", ""),
                                flight_status=row.get("FLIGHT_STATUS"),
                                seg_status=status,
                                booking_code=row.get("BOOKING_CODE"),
                                pax_status=row.get("PAX_STATUS"),
                                total_fare=float(row.get("TOTAL_FARE") or 0),
                                total_surcharges=float(row.get("TOTAL_SURCHARGES") or 0),
                                total_taxes=float(row.get("TOTAL_TAXES") or 0),
                                baggage_weight=row.get("BAGGAGE_WEIGHT"),
                                meals=row.get("MEALS"),
                                seat_code=row.get("SEAT_CODE"),
                                is_connecting=row.get("CNXSEG", "N"),
                                email=_generate_mock_email(
                                    row.get("FIRST_NAME", ""),
                                    row.get("LAST_NAME", ""),
                                    row["PNR"],
                                ),
                                phone=_generate_mock_phone(row["PNR"]),
                            )
                            session.add(booking)
                            count += 1
                            if count % 5000 == 0:
                                session.flush()
    session.commit()
    return count


def load_connections(session, data_dir: str) -> int:
    path = os.path.join(data_dir, "Connection Time.xlsx")
    wb = openpyxl.load_workbook(path)
    ws = wb["Hub ONDs"]
    count = 0
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        ond_code = row[1]
        if not ond_code:
            continue
        parts = ond_code.split("/")
        if len(parts) != 3:
            continue
        rule = ConnectionRule(
            ond_code=ond_code,
            origin=parts[0],
            hub=parts[1],
            destination=parts[2],
            min_conn_time_mins=int(row[2]) if row[2] else 55,
            max_conn_time_mins=int(row[3]) if row[3] else 1200,
            status=row[4] or "ACT",
        )
        session.add(rule)
        count += 1
    session.commit()
    return count


def load_loyalty(session, data_dir: str) -> int:
    path = os.path.join(data_dir, "Loyalty_Sample Data.xlsx")
    wb = openpyxl.load_workbook(path)
    ws = wb["Sheet1"]
    count = 0
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        loyalty_id = row[0]
        if not loyalty_id:
            continue
        member = LoyaltyMember(
            loyalty_id=str(loyalty_id),
            pax_type=row[1],
            pax_name=row[2],
            family_or_ind=row[3],
            head_of_family=str(row[4]).lower() == "yes" if row[4] else False,
            tier=row[5] or "Basic",
            available_points=int(row[6]) if row[6] else 0,
        )
        session.add(member)
        count += 1
    session.commit()
    return count


# Flights relevant to the demo scenario (SHJ hub routes)
DEMO_FLIGHTS = [
    "G9001", "G9002", "G9003", "G9004",
    "G9011", "G9012", "G9013", "G9014", "G9015", "G9016",
    "G9020", "G9021",
    "G9027", "G9028",
    "G9031", "G9032",
    "G9040", "G9041", "G9042", "G9043",
]


def load_all(data_dir: str, db_url: str | None = None):
    if db_url:
        eng = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=eng)
        Session = sessionmaker(bind=eng)
    else:
        from app.database import engine, SessionLocal
        Base.metadata.create_all(bind=engine)
        Session = SessionLocal

    session = Session()
    try:
        existing = session.query(Flight).first()
        if existing:
            print("Database already loaded, skipping ETL.")
            return

        print("Loading flight schedule...")
        n = load_flights(session, data_dir)
        print(f"  → {n} flight schedule records")

        print("Loading flight inventory...")
        n = load_inventory(session, data_dir)
        print(f"  → {n} inventory records")

        print("Loading booking data (demo flights only)...")
        n = load_bookings(session, data_dir, target_flights=DEMO_FLIGHTS)
        print(f"  → {n} booking records")

        print("Loading connection rules...")
        n = load_connections(session, data_dir)
        print(f"  → {n} connection rules")

        print("Loading loyalty data...")
        n = load_loyalty(session, data_dir)
        print(f"  → {n} loyalty members")

        print("ETL complete.")
    finally:
        session.close()


if __name__ == "__main__":
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "../data"
    load_all(data_dir)
```

- [ ] **Step 3: Write test — `backend/tests/test_loader.py`**

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.data_loader.loader import load_flights, load_connections, load_loyalty
from app.models import *  # noqa: F401,F403

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_load_flights():
    if not os.path.exists(os.path.join(DATA_DIR, "Flight Schedule.csv")):
        return
    session = _make_session()
    count = load_flights(session, DATA_DIR)
    assert count > 6000, f"Expected >6000 flights, got {count}"
    from app.models.flight import Flight
    shj_flights = session.query(Flight).filter(Flight.origin == "SHJ").count()
    assert shj_flights > 0, "Expected SHJ-origin flights"
    session.close()


def test_load_connections():
    if not os.path.exists(os.path.join(DATA_DIR, "Connection Time.xlsx")):
        return
    session = _make_session()
    count = load_connections(session, DATA_DIR)
    assert count > 30, f"Expected >30 connection rules, got {count}"
    from app.models.connection import ConnectionRule
    shj = session.query(ConnectionRule).filter(ConnectionRule.hub == "SHJ").count()
    assert shj > 0, "Expected SHJ hub rules"
    session.close()


def test_load_loyalty():
    if not os.path.exists(os.path.join(DATA_DIR, "Loyalty_Sample Data.xlsx")):
        return
    session = _make_session()
    count = load_loyalty(session, DATA_DIR)
    assert count > 0, "Expected loyalty records"
    session.close()
```

- [ ] **Step 4: Run tests**

Run:
```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_loader.py -v
```
Expected: 3 tests PASS.

- [ ] **Step 5: Run full ETL against real data**

Run:
```bash
cd backend && source venv/bin/activate && python -m app.data_loader.loader ../data
```
Expected: Output shows record counts for each table. Booking data loads only demo flights (G9001–G9043). Database file `disruption.db` created in `backend/`.

- [ ] **Step 6: Wire ETL into FastAPI startup**

Modify `backend/app/main.py` — add to the `on_startup` function:

```python
@app.on_event("startup")
def on_startup():
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    from app.data_loader.loader import load_all
    from app.core.config import settings
    load_all(settings.DATA_DIR)
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/data_loader/ backend/tests/test_loader.py backend/app/main.py
git commit -m "feat: data loader — ETL from CSV/Excel/Zip into SQLite with real Air Arabia data"
```

---

### Task 3: Passenger Module — Impact Analysis, Misconnect Detection, Priority Scoring

**Files:**
- Create: `backend/app/modules/__init__.py`
- Create: `backend/app/modules/passenger/__init__.py`
- Create: `backend/app/modules/passenger/schemas.py`
- Create: `backend/app/modules/passenger/service.py`
- Create: `backend/app/modules/passenger/router.py`
- Test: `backend/tests/test_passenger.py`

**Interfaces:**
- Consumes: `Booking`, `ConnectionRule`, `LoyaltyMember`, `DisruptionPassenger`, `Disruption`, `AuditLog` from Task 1 models; `get_db()` from Task 1
- Produces: `identify_affected(db, disruption_id: int) -> list[DisruptionPassenger]` — called by disruption service in Task 5
- Produces: `GET /api/disruptions/{disruption_id}/passengers` — returns list of `PassengerResponse`
- Produces: `GET /api/passengers/search?q={query}` — returns matching passengers

- [ ] **Step 1: Create `backend/app/modules/__init__.py` and `backend/app/modules/passenger/__init__.py`**

Both empty files.

- [ ] **Step 2: Create `backend/app/modules/passenger/schemas.py`**

```python
from pydantic import BaseModel


class PassengerResponse(BaseModel):
    id: int
    disruption_id: int
    pnr: str
    passenger_name: str | None
    pax_type: str | None
    is_connecting: bool
    is_misconnect: bool
    connecting_flight: str | None
    priority_score: int
    loyalty_tier: str | None
    total_fare: float
    original_segment: str | None
    recovery_status: str
    recovery_flight: str | None
    notified_at: str | None
    recovered_at: str | None
    email: str | None
    phone: str | None

    class Config:
        from_attributes = True
```

- [ ] **Step 3: Create `backend/app/modules/passenger/service.py`**

```python
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.booking import Booking
from app.models.connection import ConnectionRule
from app.models.disruption import Disruption, DisruptionPassenger
from app.models.loyalty import LoyaltyMember


def _score_priority(
    pax_type: str | None,
    is_connecting: bool,
    is_misconnect: bool,
    loyalty_tier: str | None,
    head_of_family: bool,
    total_fare: float,
) -> int:
    score = 0
    tier = (loyalty_tier or "").lower()
    if tier == "gold":
        score += 5
    elif tier == "silver":
        score += 3
    elif tier == "basic":
        score += 1
    if is_misconnect:
        score += 5
    elif is_connecting:
        score += 2
    if head_of_family:
        score += 2
    ptype = (pax_type or "").upper()
    if ptype in ("CHD", "CH", "CHILD"):
        score += 3
    if total_fare > 1500:
        score += 2
    return score


def identify_affected(db: Session, disruption_id: int) -> list[DisruptionPassenger]:
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        return []

    bookings = (
        db.query(Booking)
        .filter(
            Booking.flight_number == disruption.flight_number,
            Booking.seg_status != "CNX",
        )
        .all()
    )

    connection_rules = {r.ond_code: r for r in db.query(ConnectionRule).all()}
    loyalty_map = {}
    for member in db.query(LoyaltyMember).all():
        name_key = (member.pax_name or "").lower().strip()
        loyalty_map[name_key] = member

    seen_pnr_names = set()
    passengers = []

    for bk in bookings:
        pnr_name_key = f"{bk.pnr}_{bk.first_name}_{bk.last_name}"
        if pnr_name_key in seen_pnr_names:
            continue
        seen_pnr_names.add(pnr_name_key)

        is_connecting = bk.is_connecting == "Y"
        connecting_flight = None
        is_misconnect = False

        if is_connecting:
            other_segments = (
                db.query(Booking)
                .filter(
                    Booking.pnr == bk.pnr,
                    Booking.flight_number != disruption.flight_number,
                    Booking.seg_status != "CNX",
                )
                .all()
            )
            if other_segments:
                connecting_flight = other_segments[0].flight_number
                is_misconnect = True

        full_name = f"{bk.first_name or ''} {bk.last_name or ''}".strip()
        name_key = full_name.lower()
        loyalty = loyalty_map.get(name_key)
        loyalty_tier = loyalty.tier if loyalty else None
        head_of_family = loyalty.head_of_family if loyalty else False

        priority = _score_priority(
            pax_type=bk.pax_type_code,
            is_connecting=is_connecting,
            is_misconnect=is_misconnect,
            loyalty_tier=loyalty_tier,
            head_of_family=head_of_family,
            total_fare=float(bk.total_fare or 0),
        )

        dp = DisruptionPassenger(
            disruption_id=disruption_id,
            pnr=bk.pnr,
            passenger_name=full_name,
            pax_type=bk.pax_type_code,
            is_connecting=1 if is_connecting else 0,
            is_misconnect=1 if is_misconnect else 0,
            connecting_flight=connecting_flight,
            priority_score=priority,
            loyalty_tier=loyalty_tier,
            total_fare=float(bk.total_fare or 0),
            original_segment=bk.segment_code,
            recovery_status="pending",
            email=bk.email,
            phone=bk.phone,
        )
        db.add(dp)
        passengers.append(dp)

    db.flush()

    disruption.affected_pax_count = len(passengers)
    db.add(AuditLog(
        disruption_id=disruption_id,
        action="pax_identified",
        details=json.dumps({"count": len(passengers)}),
        actor="system",
    ))
    db.commit()
    return passengers


def get_disruption_passengers(
    db: Session, disruption_id: int
) -> list[DisruptionPassenger]:
    return (
        db.query(DisruptionPassenger)
        .filter(DisruptionPassenger.disruption_id == disruption_id)
        .order_by(DisruptionPassenger.priority_score.desc())
        .all()
    )


def search_passengers(db: Session, query: str) -> list[DisruptionPassenger]:
    q = query.strip()
    if len(q) == 6 and q.isalnum():
        return (
            db.query(DisruptionPassenger)
            .filter(DisruptionPassenger.pnr == q.upper())
            .all()
        )
    return (
        db.query(DisruptionPassenger)
        .filter(DisruptionPassenger.passenger_name.ilike(f"%{q}%"))
        .limit(50)
        .all()
    )
```

- [ ] **Step 4: Create `backend/app/modules/passenger/router.py`**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.passenger.schemas import PassengerResponse
from app.modules.passenger.service import get_disruption_passengers, search_passengers

router = APIRouter(prefix="/api", tags=["passengers"])


@router.get(
    "/disruptions/{disruption_id}/passengers",
    response_model=list[PassengerResponse],
)
def list_passengers(disruption_id: int, db: Session = Depends(get_db)):
    passengers = get_disruption_passengers(db, disruption_id)
    return [_to_response(p) for p in passengers]


@router.get("/passengers/search", response_model=list[PassengerResponse])
def search(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    passengers = search_passengers(db, q)
    return [_to_response(p) for p in passengers]


def _to_response(p) -> dict:
    return {
        "id": p.id,
        "disruption_id": p.disruption_id,
        "pnr": p.pnr,
        "passenger_name": p.passenger_name,
        "pax_type": p.pax_type,
        "is_connecting": bool(p.is_connecting),
        "is_misconnect": bool(p.is_misconnect),
        "connecting_flight": p.connecting_flight,
        "priority_score": p.priority_score,
        "loyalty_tier": p.loyalty_tier,
        "total_fare": float(p.total_fare or 0),
        "original_segment": p.original_segment,
        "recovery_status": p.recovery_status,
        "recovery_flight": p.recovery_flight,
        "notified_at": str(p.notified_at) if p.notified_at else None,
        "recovered_at": str(p.recovered_at) if p.recovered_at else None,
        "email": p.email,
        "phone": p.phone,
    }
```

- [ ] **Step 5: Write test — `backend/tests/test_passenger.py`**

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.booking import Booking
from app.models.connection import ConnectionRule
from app.models.disruption import Disruption
from app.modules.passenger.service import identify_affected, _score_priority


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_score_priority_misconnect_gold():
    score = _score_priority(
        pax_type="AD",
        is_connecting=True,
        is_misconnect=True,
        loyalty_tier="Gold",
        head_of_family=True,
        total_fare=2000.0,
    )
    assert score == 5 + 5 + 2 + 2  # gold + misconnect + family + high fare = 14


def test_score_priority_basic_direct():
    score = _score_priority(
        pax_type="AD",
        is_connecting=False,
        is_misconnect=False,
        loyalty_tier="Basic",
        head_of_family=False,
        total_fare=500.0,
    )
    assert score == 1  # basic only


def test_identify_affected():
    session = _make_session()
    d = Disruption(
        flight_number="G9001",
        flight_date=date(2026, 11, 22),
        disruption_type="cancellation",
        reason="technical",
    )
    session.add(d)
    session.flush()

    for i in range(5):
        session.add(Booking(
            pnr=f"PNR{i:03d}",
            first_name=f"First{i}",
            last_name=f"Last{i}",
            flight_number="G9001",
            segment_code="SHJ/JED",
            seg_status="HK",
            is_connecting="N",
            email=f"test{i}@example.com",
            phone=f"+971-50-{i}",
        ))
    session.commit()

    passengers = identify_affected(session, d.id)
    assert len(passengers) == 5

    d_updated = session.query(Disruption).first()
    assert d_updated.affected_pax_count == 5
    session.close()
```

- [ ] **Step 6: Run tests**

Run:
```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_passenger.py -v
```
Expected: 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/
git commit -m "feat: passenger module — impact analysis, misconnect detection, priority scoring"
```

---

### Task 4: Recovery Module — Alternative Generation & Acceptance

**Files:**
- Create: `backend/app/modules/recovery/__init__.py`
- Create: `backend/app/modules/recovery/schemas.py`
- Create: `backend/app/modules/recovery/service.py`
- Create: `backend/app/modules/recovery/router.py`
- Test: `backend/tests/test_recovery.py`

**Interfaces:**
- Consumes: `Flight`, `FlightInventory`, `Disruption`, `DisruptionPassenger`, `RecoveryOption`, `RecoveryCost`, `AuditLog` from Task 1; `decode_access_token` from Task 1
- Produces: `generate_alternatives_for_disruption(db, disruption_id)` — called by disruption service in Task 5
- Produces: `GET /api/recovery/{token}` — returns passenger recovery info + alternatives (used by self-service portal)
- Produces: `POST /api/recovery/{token}/accept` — accepts an alternative or requests refund

- [ ] **Step 1: Create `backend/app/modules/recovery/__init__.py`**

Empty file.

- [ ] **Step 2: Create `backend/app/modules/recovery/schemas.py`**

```python
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

    class Config:
        from_attributes = True


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
    action: str = "accept"  # "accept" or "refund"
```

- [ ] **Step 3: Create `backend/app/modules/recovery/service.py`**

```python
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.disruption import Disruption, DisruptionPassenger
from app.models.flight import Flight, FlightInventory
from app.models.recovery import RecoveryCost, RecoveryOption


def generate_alternatives_for_disruption(db: Session, disruption_id: int) -> int:
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        return 0

    passengers = (
        db.query(DisruptionPassenger)
        .filter(DisruptionPassenger.disruption_id == disruption_id)
        .all()
    )
    if not passengers:
        return 0

    first_pax = passengers[0]
    segment = first_pax.original_segment or ""
    parts = segment.split("/")
    if len(parts) != 2:
        return 0
    origin, destination = parts[0], parts[1]

    candidate_flights = (
        db.query(Flight)
        .filter(Flight.origin == origin, Flight.destination == destination)
        .all()
    )

    alternatives = []
    for cf in candidate_flights:
        if cf.flight_number == disruption.flight_number:
            continue
        total_avail = (
            db.query(FlightInventory)
            .filter(FlightInventory.flight_number == cf.flight_number)
            .with_entities(
                FlightInventory.flight_number,
                FlightInventory.available_seats,
            )
            .all()
        )
        avail_seats = sum(row.available_seats for row in total_avail)
        if avail_seats <= 0:
            continue
        alternatives.append({
            "flight_number": cf.flight_number,
            "origin": origin,
            "destination": destination,
            "departure_time": cf.dep_time_local,
            "arrival_time": cf.arr_time_local,
            "available_seats": avail_seats,
        })

    alternatives.sort(key=lambda a: a["departure_time"])
    alternatives = alternatives[:3]

    total_options = 0
    for pax in passengers:
        for rank, alt in enumerate(alternatives, 1):
            opt = RecoveryOption(
                disruption_id=disruption_id,
                pnr=pax.pnr,
                flight_number=alt["flight_number"],
                origin=alt["origin"],
                destination=alt["destination"],
                departure_time=alt["departure_time"],
                arrival_time=alt["arrival_time"],
                available_seats=alt["available_seats"],
                fare_difference=0,
                rank=rank,
                status="offered",
            )
            db.add(opt)
            total_options += 1

    db.add(AuditLog(
        disruption_id=disruption_id,
        action="alternatives_generated",
        details=json.dumps({
            "alternative_flights": [a["flight_number"] for a in alternatives],
            "pax_count": len(passengers),
        }),
        actor="system",
    ))
    db.commit()
    return total_options


def get_recovery_info(db: Session, disruption_id: int, pnr: str) -> dict | None:
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        return None

    pax = (
        db.query(DisruptionPassenger)
        .filter(
            DisruptionPassenger.disruption_id == disruption_id,
            DisruptionPassenger.pnr == pnr,
        )
        .first()
    )
    if not pax:
        return None

    options = (
        db.query(RecoveryOption)
        .filter(
            RecoveryOption.disruption_id == disruption_id,
            RecoveryOption.pnr == pnr,
            RecoveryOption.status == "offered",
        )
        .order_by(RecoveryOption.rank)
        .all()
    )

    if pax.recovery_status == "pending":
        pax.recovery_status = "options_viewed"
        db.commit()

    return {
        "disruption_type": disruption.disruption_type,
        "flight_number": disruption.flight_number,
        "flight_date": str(disruption.flight_date),
        "passenger_name": pax.passenger_name,
        "pnr": pax.pnr,
        "original_segment": pax.original_segment,
        "recovery_status": pax.recovery_status,
        "options": options,
    }


def accept_alternative(db: Session, disruption_id: int, pnr: str, option_id: int):
    option = (
        db.query(RecoveryOption)
        .filter(RecoveryOption.id == option_id, RecoveryOption.pnr == pnr)
        .first()
    )
    if not option:
        return None

    option.status = "accepted"

    other_options = (
        db.query(RecoveryOption)
        .filter(
            RecoveryOption.disruption_id == disruption_id,
            RecoveryOption.pnr == pnr,
            RecoveryOption.id != option_id,
        )
        .all()
    )
    for o in other_options:
        o.status = "declined"

    pax = (
        db.query(DisruptionPassenger)
        .filter(
            DisruptionPassenger.disruption_id == disruption_id,
            DisruptionPassenger.pnr == pnr,
        )
        .first()
    )
    if pax:
        pax.recovery_status = "self_served"
        pax.recovery_flight = option.flight_number
        pax.recovered_at = datetime.now(timezone.utc)

    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if disruption:
        recovered = (
            db.query(DisruptionPassenger)
            .filter(
                DisruptionPassenger.disruption_id == disruption_id,
                DisruptionPassenger.recovery_status.in_(["self_served", "manually_handled"]),
            )
            .count()
        )
        disruption.recovered_pax_count = recovered

    if float(option.fare_difference or 0) != 0:
        db.add(RecoveryCost(
            disruption_id=disruption_id,
            pnr=pnr,
            cost_type="rebooking_fare_diff",
            amount=float(option.fare_difference),
        ))

    db.add(AuditLog(
        disruption_id=disruption_id,
        pnr=pnr,
        action="alternative_accepted",
        details=json.dumps({
            "flight": option.flight_number,
            "fare_diff": float(option.fare_difference or 0),
        }),
        actor="passenger",
    ))
    db.commit()
    return option


def request_refund(db: Session, disruption_id: int, pnr: str):
    pax = (
        db.query(DisruptionPassenger)
        .filter(
            DisruptionPassenger.disruption_id == disruption_id,
            DisruptionPassenger.pnr == pnr,
        )
        .first()
    )
    if not pax:
        return None

    pax.recovery_status = "refunded"
    pax.recovered_at = datetime.now(timezone.utc)

    options = (
        db.query(RecoveryOption)
        .filter(
            RecoveryOption.disruption_id == disruption_id,
            RecoveryOption.pnr == pnr,
        )
        .all()
    )
    for o in options:
        o.status = "declined"

    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if disruption:
        recovered = (
            db.query(DisruptionPassenger)
            .filter(
                DisruptionPassenger.disruption_id == disruption_id,
                DisruptionPassenger.recovery_status.in_(
                    ["self_served", "manually_handled", "refunded"]
                ),
            )
            .count()
        )
        disruption.recovered_pax_count = recovered

    db.add(RecoveryCost(
        disruption_id=disruption_id,
        pnr=pnr,
        cost_type="refund",
        amount=float(pax.total_fare or 0),
    ))
    db.add(AuditLog(
        disruption_id=disruption_id,
        pnr=pnr,
        action="refund_requested",
        details=json.dumps({"fare": float(pax.total_fare or 0)}),
        actor="passenger",
    ))
    db.commit()
    return pax
```

- [ ] **Step 4: Create `backend/app/modules/recovery/router.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.modules.recovery.schemas import AcceptRequest, RecoveryInfoResponse
from app.modules.recovery.service import (
    accept_alternative,
    get_recovery_info,
    request_refund,
)

router = APIRouter(prefix="/api/recovery", tags=["recovery"])


def _decode_token(token: str) -> dict:
    try:
        return decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired recovery link")


@router.get("/{token}", response_model=RecoveryInfoResponse)
def get_recovery(token: str, db: Session = Depends(get_db)):
    payload = _decode_token(token)
    info = get_recovery_info(db, payload["disruption_id"], payload["pnr"])
    if not info:
        raise HTTPException(status_code=404, detail="Recovery info not found")
    return info


@router.post("/{token}/accept")
def accept(token: str, body: AcceptRequest, db: Session = Depends(get_db)):
    payload = _decode_token(token)
    disruption_id = payload["disruption_id"]
    pnr = payload["pnr"]

    if body.action == "refund":
        result = request_refund(db, disruption_id, pnr)
        if not result:
            raise HTTPException(status_code=404, detail="Passenger not found")
        return {"status": "refunded", "message": "Refund request submitted"}

    if not body.option_id:
        raise HTTPException(status_code=400, detail="option_id required for accept")

    result = accept_alternative(db, disruption_id, pnr, body.option_id)
    if not result:
        raise HTTPException(status_code=404, detail="Option not found")
    return {
        "status": "accepted",
        "flight_number": result.flight_number,
        "departure_time": result.departure_time,
    }
```

- [ ] **Step 5: Write test — `backend/tests/test_recovery.py`**

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.booking import Booking
from app.models.disruption import Disruption, DisruptionPassenger
from app.models.flight import Flight, FlightInventory
from app.models.recovery import RecoveryOption
from app.modules.recovery.service import (
    accept_alternative,
    generate_alternatives_for_disruption,
    request_refund,
)


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _seed(session):
    d = Disruption(
        flight_number="G9001",
        flight_date=date(2026, 11, 22),
        disruption_type="cancellation",
    )
    session.add(d)
    session.flush()

    session.add(DisruptionPassenger(
        disruption_id=d.id,
        pnr="ABC123",
        passenger_name="Test User",
        original_segment="SHJ/JED",
        recovery_status="pending",
        total_fare=500,
    ))

    session.add(Flight(
        flight_number="G9001", origin="SHJ", destination="JED",
        dep_time_local="09:00", arr_time_local="10:50",
        frequency="MON:TUE:WED", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.add(Flight(
        flight_number="G9003", origin="SHJ", destination="JED",
        dep_time_local="13:00", arr_time_local="14:50",
        frequency="MON:TUE:WED", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))

    session.add(FlightInventory(
        flight_number="G9003",
        departure_datetime_local="2026-11-22 13:00:00",
        departure_datetime_zulu="2026-11-22 09:00:00",
        aircraft_model="A320-174", adult_capacity=174,
        booking_class="E70", allocated_seats=174, available_seats=45,
    ))
    session.commit()
    return d


def test_generate_alternatives():
    session = _make_session()
    d = _seed(session)
    count = generate_alternatives_for_disruption(session, d.id)
    assert count > 0
    options = session.query(RecoveryOption).filter(RecoveryOption.pnr == "ABC123").all()
    assert len(options) == 1
    assert options[0].flight_number == "G9003"
    session.close()


def test_accept_alternative():
    session = _make_session()
    d = _seed(session)
    generate_alternatives_for_disruption(session, d.id)
    opt = session.query(RecoveryOption).filter(RecoveryOption.pnr == "ABC123").first()
    result = accept_alternative(session, d.id, "ABC123", opt.id)
    assert result is not None
    assert result.status == "accepted"
    pax = session.query(DisruptionPassenger).filter(DisruptionPassenger.pnr == "ABC123").first()
    assert pax.recovery_status == "self_served"
    assert pax.recovery_flight == "G9003"
    session.close()


def test_request_refund():
    session = _make_session()
    d = _seed(session)
    result = request_refund(session, d.id, "ABC123")
    assert result is not None
    assert result.recovery_status == "refunded"
    session.close()
```

- [ ] **Step 6: Run tests**

Run:
```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_recovery.py -v
```
Expected: 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/recovery/ backend/tests/test_recovery.py
git commit -m "feat: recovery module — alternative generation, acceptance, and refund flows"
```

---

### Task 5: Disruption Module — Event Creation, Pipeline Orchestration, WebSocket

**Files:**
- Create: `backend/app/modules/disruption/__init__.py`
- Create: `backend/app/modules/disruption/schemas.py`
- Create: `backend/app/modules/disruption/service.py`
- Create: `backend/app/modules/disruption/router.py`
- Modify: `backend/app/main.py` — register all routers
- Test: `backend/tests/test_disruption.py`

**Interfaces:**
- Consumes: `identify_affected` from Task 3; `generate_alternatives_for_disruption` from Task 4; `manager` from Task 1 websocket; all ORM models
- Produces: `POST /api/disruptions` — creates disruption, runs full pipeline, broadcasts via WebSocket
- Produces: `GET /api/disruptions` — lists all disruptions
- Produces: `GET /api/disruptions/{id}` — single disruption detail

- [ ] **Step 1: Create `backend/app/modules/disruption/__init__.py`**

Empty file.

- [ ] **Step 2: Create `backend/app/modules/disruption/schemas.py`**

```python
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

    class Config:
        from_attributes = True
```

- [ ] **Step 3: Create `backend/app/modules/disruption/service.py`**

```python
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.disruption import Disruption
from app.models.flight import Flight


def create_disruption(
    db: Session,
    flight_number: str,
    flight_date: str,
    disruption_type: str,
    reason: str,
) -> Disruption:
    parsed_date = datetime.strptime(flight_date, "%Y-%m-%d").date()

    disruption = Disruption(
        flight_number=flight_number,
        flight_date=parsed_date,
        disruption_type=disruption_type,
        reason=reason,
    )
    db.add(disruption)
    db.flush()

    flight = db.query(Flight).filter(Flight.flight_number == flight_number).first()
    route = f"{flight.origin}/{flight.destination}" if flight else "unknown"

    db.add(AuditLog(
        disruption_id=disruption.id,
        action="disruption_created",
        details=json.dumps({
            "flight": flight_number,
            "date": flight_date,
            "type": disruption_type,
            "reason": reason,
            "route": route,
        }),
        actor="operator",
    ))
    db.commit()
    return disruption


def get_disruptions(db: Session) -> list[Disruption]:
    return db.query(Disruption).order_by(Disruption.created_at.desc()).all()


def get_disruption(db: Session, disruption_id: int) -> Disruption | None:
    return db.query(Disruption).filter(Disruption.id == disruption_id).first()


def get_flight_info(db: Session, flight_number: str) -> dict | None:
    flight = db.query(Flight).filter(Flight.flight_number == flight_number).first()
    if not flight:
        return None
    return {
        "flight_number": flight.flight_number,
        "origin": flight.origin,
        "destination": flight.destination,
        "dep_time": flight.dep_time_local,
        "arr_time": flight.arr_time_local,
    }
```

- [ ] **Step 4: Create `backend/app/modules/disruption/router.py`**

```python
import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.websocket import manager
from app.database import get_db, SessionLocal
from app.modules.disruption.schemas import CreateDisruptionRequest, DisruptionResponse
from app.modules.disruption.service import (
    create_disruption,
    get_disruption,
    get_disruptions,
    get_flight_info,
)
from app.modules.passenger.service import identify_affected
from app.modules.recovery.service import generate_alternatives_for_disruption

router = APIRouter(prefix="/api/disruptions", tags=["disruptions"])


def _run_pipeline(disruption_id: int):
    db = SessionLocal()
    try:
        identify_affected(db, disruption_id)
        generate_alternatives_for_disruption(db, disruption_id)
    finally:
        db.close()


@router.post("", response_model=DisruptionResponse)
async def create(body: CreateDisruptionRequest, db: Session = Depends(get_db)):
    disruption = create_disruption(
        db, body.flight_number, body.flight_date, body.disruption_type, body.reason
    )
    flight_info = get_flight_info(db, body.flight_number)

    _run_pipeline(disruption.id)

    db.refresh(disruption)

    await manager.broadcast("disruption_created", {
        "id": disruption.id,
        "flight_number": disruption.flight_number,
        "flight_date": str(disruption.flight_date),
        "disruption_type": disruption.disruption_type,
        "affected_pax_count": disruption.affected_pax_count,
        "flight_info": flight_info,
    })

    return _to_response(disruption)


@router.get("", response_model=list[DisruptionResponse])
def list_all(db: Session = Depends(get_db)):
    return [_to_response(d) for d in get_disruptions(db)]


@router.get("/{disruption_id}", response_model=DisruptionResponse)
def get_one(disruption_id: int, db: Session = Depends(get_db)):
    d = get_disruption(db, disruption_id)
    if not d:
        raise HTTPException(status_code=404, detail="Disruption not found")
    return _to_response(d)


def _to_response(d) -> dict:
    return {
        "id": d.id,
        "flight_number": d.flight_number,
        "flight_date": str(d.flight_date),
        "disruption_type": d.disruption_type,
        "reason": d.reason,
        "created_at": str(d.created_at) if d.created_at else None,
        "status": d.status,
        "affected_pax_count": d.affected_pax_count or 0,
        "recovered_pax_count": d.recovered_pax_count or 0,
    }
```

- [ ] **Step 5: Create notification and dashboard module stubs (wired in Task 6 and 7)**

Create `backend/app/modules/notification/__init__.py` and `backend/app/modules/dashboard/__init__.py` — both empty.

- [ ] **Step 6: Wire all routers into `backend/app/main.py`**

Replace `backend/app/main.py` with:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.websocket import manager
from app.database import Base, engine

app = FastAPI(title="Air Arabia Disruption Management", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    from app.data_loader.loader import load_all
    load_all(settings.DATA_DIR)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


from app.modules.disruption.router import router as disruption_router
from app.modules.passenger.router import router as passenger_router
from app.modules.recovery.router import router as recovery_router

app.include_router(disruption_router)
app.include_router(passenger_router)
app.include_router(recovery_router)
```

- [ ] **Step 7: Write test — `backend/tests/test_disruption.py`**

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.modules.disruption.service import create_disruption, get_disruptions


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_create_disruption():
    session = _make_session()
    from app.models.flight import Flight
    session.add(Flight(
        flight_number="G9001", origin="SHJ", destination="JED",
        dep_time_local="09:00", arr_time_local="10:50",
        frequency="DAILY", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.commit()

    d = create_disruption(session, "G9001", "2026-11-22", "cancellation", "weather")
    assert d.id is not None
    assert d.flight_number == "G9001"
    assert d.disruption_type == "cancellation"
    session.close()


def test_list_disruptions():
    session = _make_session()
    from app.models.flight import Flight
    session.add(Flight(
        flight_number="G9001", origin="SHJ", destination="JED",
        dep_time_local="09:00", arr_time_local="10:50",
        frequency="DAILY", schedule_start=date(2026, 1, 1),
        schedule_end=date(2027, 12, 31),
    ))
    session.commit()
    create_disruption(session, "G9001", "2026-11-22", "cancellation", "tech")
    create_disruption(session, "G9001", "2026-11-23", "delay", "weather")
    results = get_disruptions(session)
    assert len(results) == 2
    session.close()
```

- [ ] **Step 8: Run all backend tests**

Run:
```bash
cd backend && source venv/bin/activate && python -m pytest tests/ -v
```
Expected: All tests PASS (database, loader, passenger, recovery, disruption).

- [ ] **Step 9: Commit**

```bash
git add backend/
git commit -m "feat: disruption module — event creation, full recovery pipeline, WebSocket broadcast"
```

---

### Task 6: Notification Module — JWT Deep Links & Email Simulation

**Files:**
- Create: `backend/app/modules/notification/schemas.py`
- Create: `backend/app/modules/notification/service.py`
- Create: `backend/app/modules/notification/router.py`
- Test: `backend/tests/test_notification.py`

**Interfaces:**
- Consumes: `DisruptionPassenger`, `Disruption`, `AuditLog` from models; `create_access_token` from core/security; `manager` from websocket
- Produces: `POST /api/notifications/{disruption_id}/send` — sends notifications to all pending passengers, returns count
- Produces: `GET /api/notifications/{disruption_id}/status` — returns notification stats

- [ ] **Step 1: Create `backend/app/modules/notification/schemas.py`**

```python
from pydantic import BaseModel


class NotificationStatusResponse(BaseModel):
    disruption_id: int
    total_passengers: int
    notified: int
    pending: int


class SendNotificationsResponse(BaseModel):
    disruption_id: int
    sent_count: int
    deep_links: list[dict]
```

- [ ] **Step 2: Create `backend/app/modules/notification/service.py`**

```python
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.audit import AuditLog
from app.models.disruption import Disruption, DisruptionPassenger


def send_notifications(db: Session, disruption_id: int) -> dict:
    disruption = db.query(Disruption).filter(Disruption.id == disruption_id).first()
    if not disruption:
        return {"sent_count": 0, "deep_links": []}

    passengers = (
        db.query(DisruptionPassenger)
        .filter(
            DisruptionPassenger.disruption_id == disruption_id,
            DisruptionPassenger.recovery_status == "pending",
        )
        .all()
    )

    deep_links = []
    for pax in passengers:
        token = create_access_token({
            "disruption_id": disruption_id,
            "pnr": pax.pnr,
        })
        deep_link = f"{settings.FRONTEND_URL}/recover/{token}"

        print(
            f"[NOTIFICATION] To: {pax.email} | "
            f"Flight {disruption.flight_number} {disruption.disruption_type} | "
            f"Link: {deep_link}"
        )

        pax.notified_at = datetime.now(timezone.utc)
        pax.recovery_status = "notified"

        db.add(AuditLog(
            disruption_id=disruption_id,
            pnr=pax.pnr,
            action="notification_sent",
            details=json.dumps({"email": pax.email, "channel": "email"}),
            actor="system",
        ))

        deep_links.append({
            "pnr": pax.pnr,
            "name": pax.passenger_name,
            "email": pax.email,
            "deep_link": deep_link,
        })

    db.commit()

    return {
        "disruption_id": disruption_id,
        "sent_count": len(deep_links),
        "deep_links": deep_links,
    }


def get_notification_status(db: Session, disruption_id: int) -> dict:
    total = (
        db.query(DisruptionPassenger)
        .filter(DisruptionPassenger.disruption_id == disruption_id)
        .count()
    )
    notified = (
        db.query(DisruptionPassenger)
        .filter(
            DisruptionPassenger.disruption_id == disruption_id,
            DisruptionPassenger.notified_at.isnot(None),
        )
        .count()
    )
    return {
        "disruption_id": disruption_id,
        "total_passengers": total,
        "notified": notified,
        "pending": total - notified,
    }
```

- [ ] **Step 3: Create `backend/app/modules/notification/router.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.websocket import manager
from app.database import get_db
from app.modules.notification.schemas import (
    NotificationStatusResponse,
    SendNotificationsResponse,
)
from app.modules.notification.service import get_notification_status, send_notifications

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.post("/{disruption_id}/send", response_model=SendNotificationsResponse)
async def send(disruption_id: int, db: Session = Depends(get_db)):
    result = send_notifications(db, disruption_id)
    await manager.broadcast("notifications_sent", {
        "disruption_id": disruption_id,
        "count": result["sent_count"],
    })
    return result


@router.get("/{disruption_id}/status", response_model=NotificationStatusResponse)
def status(disruption_id: int, db: Session = Depends(get_db)):
    return get_notification_status(db, disruption_id)
```

- [ ] **Step 4: Register notification router in `backend/app/main.py`**

Add at the end of `main.py`:

```python
from app.modules.notification.router import router as notification_router
app.include_router(notification_router)
```

- [ ] **Step 5: Write test — `backend/tests/test_notification.py`**

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.disruption import Disruption, DisruptionPassenger
from app.modules.notification.service import send_notifications, get_notification_status


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_send_notifications():
    session = _make_session()
    d = Disruption(
        flight_number="G9001",
        flight_date=date(2026, 11, 22),
        disruption_type="cancellation",
    )
    session.add(d)
    session.flush()

    for i in range(3):
        session.add(DisruptionPassenger(
            disruption_id=d.id,
            pnr=f"PNR{i:03d}",
            passenger_name=f"Test {i}",
            recovery_status="pending",
            email=f"test{i}@example.com",
        ))
    session.commit()

    result = send_notifications(session, d.id)
    assert result["sent_count"] == 3
    assert len(result["deep_links"]) == 3

    for link in result["deep_links"]:
        assert "recover/" in link["deep_link"]

    status = get_notification_status(session, d.id)
    assert status["notified"] == 3
    assert status["pending"] == 0
    session.close()
```

- [ ] **Step 6: Run tests**

Run:
```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_notification.py -v
```
Expected: 1 test PASSES.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/notification/ backend/tests/test_notification.py backend/app/main.py
git commit -m "feat: notification module — JWT deep links, email simulation, notification status"
```

---

### Task 7: Dashboard Module — KPIs, Flights List, WebSocket Endpoint

**Files:**
- Create: `backend/app/modules/dashboard/schemas.py`
- Create: `backend/app/modules/dashboard/service.py`
- Create: `backend/app/modules/dashboard/router.py`
- Modify: `backend/app/main.py` — register dashboard router
- Test: `backend/tests/test_dashboard.py`

**Interfaces:**
- Consumes: `Disruption`, `DisruptionPassenger`, `RecoveryCost`, `Flight` from models
- Produces: `GET /api/dashboard/kpis` — returns all KPI metrics
- Produces: `GET /api/dashboard/flights` — returns list of all flights (for disruption trigger dropdown)
- Produces: `GET /api/dashboard/disruptions/{id}/summary` — single disruption summary with recovery stats

- [ ] **Step 1: Create `backend/app/modules/dashboard/schemas.py`**

```python
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

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Create `backend/app/modules/dashboard/service.py`**

```python
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.disruption import Disruption, DisruptionPassenger
from app.models.flight import Flight
from app.models.recovery import RecoveryCost


def get_kpis(db: Session, disruption_id: int | None = None) -> dict:
    q = db.query(DisruptionPassenger)
    if disruption_id:
        q = q.filter(DisruptionPassenger.disruption_id == disruption_id)

    total = q.count()
    recovered = q.filter(
        DisruptionPassenger.recovery_status.in_(["self_served", "manually_handled", "refunded"])
    ).count()
    self_served = q.filter(DisruptionPassenger.recovery_status == "self_served").count()
    refunded = q.filter(DisruptionPassenger.recovery_status == "refunded").count()
    pending = q.filter(DisruptionPassenger.recovery_status == "pending").count()
    notified = q.filter(DisruptionPassenger.recovery_status == "notified").count()

    self_service_rate = (self_served / recovered * 100) if recovered > 0 else 0.0

    avg_time = None
    recovered_pax = (
        q.filter(DisruptionPassenger.recovered_at.isnot(None))
        .all()
    )
    if recovered_pax:
        times = []
        for pax in recovered_pax:
            d = db.query(Disruption).filter(Disruption.id == pax.disruption_id).first()
            if d and d.created_at and pax.recovered_at:
                diff = (pax.recovered_at - d.created_at).total_seconds()
                times.append(diff)
        if times:
            avg_time = sum(times) / len(times)

    cost_q = db.query(func.sum(RecoveryCost.amount))
    if disruption_id:
        cost_q = cost_q.filter(RecoveryCost.disruption_id == disruption_id)
    total_cost = cost_q.scalar() or 0

    return {
        "affected_pax_count": total,
        "recovered_pax_count": recovered,
        "self_service_count": self_served,
        "refund_count": refunded,
        "self_service_rate": round(self_service_rate, 1),
        "avg_recovery_time_seconds": round(avg_time, 1) if avg_time else None,
        "total_recovery_cost": float(total_cost),
        "pending_count": pending,
        "notified_count": notified,
    }


def get_flights(db: Session) -> list[dict]:
    flights = (
        db.query(Flight)
        .group_by(Flight.flight_number)
        .order_by(Flight.flight_number)
        .all()
    )
    seen = set()
    result = []
    for f in flights:
        if f.flight_number in seen:
            continue
        seen.add(f.flight_number)
        result.append({
            "flight_number": f.flight_number,
            "origin": f.origin,
            "destination": f.destination,
            "dep_time": f.dep_time_local,
            "arr_time": f.arr_time_local,
        })
    return result
```

- [ ] **Step 3: Create `backend/app/modules/dashboard/router.py`**

```python
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
```

- [ ] **Step 4: Register dashboard router in `backend/app/main.py`**

Add at the end of `main.py`:

```python
from app.modules.dashboard.router import router as dashboard_router
app.include_router(dashboard_router)
```

- [ ] **Step 5: Write test — `backend/tests/test_dashboard.py`**

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.disruption import Disruption, DisruptionPassenger
from app.models.recovery import RecoveryCost
from app.modules.dashboard.service import get_kpis


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_kpis():
    session = _make_session()
    now = datetime.now(timezone.utc)
    d = Disruption(
        flight_number="G9001",
        flight_date=date(2026, 11, 22),
        disruption_type="cancellation",
        created_at=now,
    )
    session.add(d)
    session.flush()

    session.add(DisruptionPassenger(
        disruption_id=d.id, pnr="A01", recovery_status="self_served",
        recovered_at=now + timedelta(minutes=5),
    ))
    session.add(DisruptionPassenger(
        disruption_id=d.id, pnr="A02", recovery_status="notified",
    ))
    session.add(DisruptionPassenger(
        disruption_id=d.id, pnr="A03", recovery_status="pending",
    ))
    session.add(RecoveryCost(
        disruption_id=d.id, pnr="A01", cost_type="rebooking_fare_diff", amount=150,
    ))
    session.commit()

    kpis = get_kpis(session, d.id)
    assert kpis["affected_pax_count"] == 3
    assert kpis["recovered_pax_count"] == 1
    assert kpis["self_service_count"] == 1
    assert kpis["self_service_rate"] == 100.0
    assert kpis["total_recovery_cost"] == 150.0
    assert kpis["pending_count"] == 1
    assert kpis["notified_count"] == 1
    session.close()
```

- [ ] **Step 6: Run all backend tests**

Run:
```bash
cd backend && source venv/bin/activate && python -m pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 7: Start server and test API end-to-end manually**

Run:
```bash
cd backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then verify in another terminal:
```bash
# Health check
curl http://localhost:8000/api/health

# List flights
curl http://localhost:8000/api/dashboard/flights | python3 -m json.tool | head -20

# Trigger a disruption
curl -X POST http://localhost:8000/api/disruptions \
  -H "Content-Type: application/json" \
  -d '{"flight_number":"G9001","flight_date":"2027-03-04","disruption_type":"cancellation","reason":"technical"}'

# Check affected passengers
curl http://localhost:8000/api/disruptions/1/passengers | python3 -m json.tool | head -40

# Get KPIs
curl http://localhost:8000/api/dashboard/kpis?disruption_id=1
```

Expected: Disruption creates, passengers identified with priority scores, KPIs computed.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: dashboard module — KPIs, flights list, full API wiring complete"
```

---

### Task 8: Frontend Foundation — React + Vite + Tailwind + Routing + API Client

**Files:**
- Create: `frontend/` via Vite scaffold
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/disruptions.ts`
- Create: `frontend/src/api/recovery.ts`
- Create: `frontend/src/api/dashboard.ts`
- Create: `frontend/src/hooks/useWebSocket.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/features/shared/KpiCard.tsx`
- Create: `frontend/src/features/shared/StatusBadge.tsx`
- Create: `frontend/src/features/shared/FlightCard.tsx`

**Interfaces:**
- Produces: `apiClient` — configured fetch wrapper for all API calls
- Produces: React Query hooks: `useDisruptions()`, `usePassengers(id)`, `useKpis(id)`, `useFlights()`, `useRecoveryInfo(token)` — used by dashboard and self-service pages
- Produces: `useWebSocket()` hook — connects to `ws://localhost:8000/ws/dashboard`, returns latest event
- Produces: Shared UI components — used by Task 9 and Task 10

- [ ] **Step 1: Scaffold React + Vite project**

Run:
```bash
cd /home/sarvadnya-jawle/Desktop/Flight-Passenger-Disruption-Management && npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install -D tailwindcss @tailwindcss/vite
npm install @tanstack/react-query react-router-dom
```

- [ ] **Step 2: Configure Tailwind**

Replace `frontend/src/index.css` with:
```css
@import "tailwindcss";
```

Add Tailwind plugin to `frontend/vite.config.ts`:
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
```

- [ ] **Step 3: Create `frontend/src/api/client.ts`**

```typescript
const BASE_URL = "/api";

export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}
```

- [ ] **Step 4: Create `frontend/src/api/disruptions.ts`**

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";

export interface Disruption {
  id: number;
  flight_number: string;
  flight_date: string;
  disruption_type: string;
  reason: string | null;
  created_at: string | null;
  status: string;
  affected_pax_count: number;
  recovered_pax_count: number;
}

export interface Passenger {
  id: number;
  disruption_id: number;
  pnr: string;
  passenger_name: string | null;
  pax_type: string | null;
  is_connecting: boolean;
  is_misconnect: boolean;
  connecting_flight: string | null;
  priority_score: number;
  loyalty_tier: string | null;
  total_fare: number;
  original_segment: string | null;
  recovery_status: string;
  recovery_flight: string | null;
  notified_at: string | null;
  recovered_at: string | null;
  email: string | null;
  phone: string | null;
}

export function useDisruptions() {
  return useQuery({
    queryKey: ["disruptions"],
    queryFn: () => apiFetch<Disruption[]>("/disruptions"),
    refetchInterval: 5000,
  });
}

export function usePassengers(disruptionId: number | null) {
  return useQuery({
    queryKey: ["passengers", disruptionId],
    queryFn: () =>
      apiFetch<Passenger[]>(`/disruptions/${disruptionId}/passengers`),
    enabled: !!disruptionId,
    refetchInterval: 3000,
  });
}

export function useSearchPassengers(query: string) {
  return useQuery({
    queryKey: ["search", query],
    queryFn: () => apiFetch<Passenger[]>(`/passengers/search?q=${query}`),
    enabled: query.length >= 2,
  });
}

export function useCreateDisruption() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      flight_number: string;
      flight_date: string;
      disruption_type: string;
      reason: string;
    }) =>
      apiFetch<Disruption>("/disruptions", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["disruptions"] }),
  });
}

export function useSendNotifications() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (disruptionId: number) =>
      apiFetch<{ sent_count: number; deep_links: Array<{ pnr: string; deep_link: string }> }>(
        `/notifications/${disruptionId}/send`,
        { method: "POST" }
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["passengers"] });
      qc.invalidateQueries({ queryKey: ["kpis"] });
    },
  });
}
```

- [ ] **Step 5: Create `frontend/src/api/dashboard.ts`**

```typescript
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";

export interface Kpis {
  affected_pax_count: number;
  recovered_pax_count: number;
  self_service_count: number;
  refund_count: number;
  self_service_rate: number;
  avg_recovery_time_seconds: number | null;
  total_recovery_cost: number;
  pending_count: number;
  notified_count: number;
}

export interface FlightItem {
  flight_number: string;
  origin: string;
  destination: string;
  dep_time: string;
  arr_time: string;
}

export function useKpis(disruptionId: number | null) {
  return useQuery({
    queryKey: ["kpis", disruptionId],
    queryFn: () =>
      apiFetch<Kpis>(
        `/dashboard/kpis${disruptionId ? `?disruption_id=${disruptionId}` : ""}`
      ),
    refetchInterval: 3000,
  });
}

export function useFlights() {
  return useQuery({
    queryKey: ["flights"],
    queryFn: () => apiFetch<FlightItem[]>("/dashboard/flights"),
  });
}
```

- [ ] **Step 6: Create `frontend/src/api/recovery.ts`**

```typescript
import { useQuery, useMutation } from "@tanstack/react-query";
import { apiFetch } from "./client";

export interface RecoveryOption {
  id: number;
  flight_number: string;
  origin: string | null;
  destination: string | null;
  departure_time: string | null;
  arrival_time: string | null;
  available_seats: number;
  fare_difference: number;
  rank: number;
  status: string;
}

export interface RecoveryInfo {
  disruption_type: string;
  flight_number: string;
  flight_date: string;
  passenger_name: string | null;
  pnr: string;
  original_segment: string | null;
  recovery_status: string;
  options: RecoveryOption[];
}

export function useRecoveryInfo(token: string | undefined) {
  return useQuery({
    queryKey: ["recovery", token],
    queryFn: () => apiFetch<RecoveryInfo>(`/recovery/${token}`),
    enabled: !!token,
  });
}

export function useAcceptOption(token: string | undefined) {
  return useMutation({
    mutationFn: (body: { option_id?: number; action: string }) =>
      apiFetch(`/recovery/${token}/accept`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}
```

- [ ] **Step 7: Create `frontend/src/hooks/useWebSocket.ts`**

```typescript
import { useEffect, useRef, useState } from "react";

interface WsEvent {
  type: string;
  data: Record<string, unknown>;
}

export function useWebSocket() {
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/dashboard`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        setLastEvent(JSON.parse(event.data));
      } catch {}
    };

    ws.onclose = () => {
      setTimeout(() => {
        wsRef.current = new WebSocket(
          `${proto}//${window.location.host}/ws/dashboard`
        );
      }, 2000);
    };

    return () => ws.close();
  }, []);

  return lastEvent;
}
```

- [ ] **Step 8: Create shared components**

Create `frontend/src/features/shared/KpiCard.tsx`:
```tsx
export function KpiCard({
  label,
  value,
  unit,
  color = "text-gray-900",
}: {
  label: string;
  value: string | number;
  unit?: string;
  color?: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${color}`}>
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-gray-400">{unit}</span>}
      </p>
    </div>
  );
}
```

Create `frontend/src/features/shared/StatusBadge.tsx`:
```tsx
const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  notified: "bg-blue-100 text-blue-700",
  options_viewed: "bg-yellow-100 text-yellow-700",
  self_served: "bg-green-100 text-green-700",
  manually_handled: "bg-orange-100 text-orange-700",
  refunded: "bg-purple-100 text-purple-700",
};

export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] || "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status.replace("_", " ")}
    </span>
  );
}
```

Create `frontend/src/features/shared/FlightCard.tsx`:
```tsx
export function FlightCard({
  flightNumber,
  origin,
  destination,
  depTime,
  arrTime,
  seats,
  fareDiff,
  onSelect,
  selected,
}: {
  flightNumber: string;
  origin: string;
  destination: string;
  depTime: string;
  arrTime: string;
  seats?: number;
  fareDiff?: number;
  onSelect?: () => void;
  selected?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border-2 p-4 ${
        selected ? "border-green-500 bg-green-50" : "border-gray-200 bg-white"
      }`}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-lg font-bold text-gray-900">{flightNumber}</p>
          <p className="text-sm text-gray-500">
            {origin} → {destination}
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm font-medium">
            {depTime} → {arrTime}
          </p>
          {seats !== undefined && (
            <p className="text-xs text-gray-400">{seats} seats available</p>
          )}
        </div>
      </div>
      {fareDiff !== undefined && fareDiff !== 0 && (
        <p className="mt-2 text-sm text-orange-600">
          Fare difference: AED {fareDiff.toFixed(0)}
        </p>
      )}
      {onSelect && (
        <button
          onClick={onSelect}
          className="mt-3 w-full rounded-md bg-[#CE1126] px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
        >
          Select This Flight
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 9: Create `frontend/src/App.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { RecoveryPage } from "./features/self-service/RecoveryPage";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/recover/:token" element={<RecoveryPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 10: Create placeholder pages for dashboard and self-service**

Create `frontend/src/features/dashboard/DashboardPage.tsx`:
```tsx
export function DashboardPage() {
  return <div className="p-8 text-2xl font-bold text-gray-900">OCC Dashboard — loading...</div>;
}
```

Create `frontend/src/features/self-service/RecoveryPage.tsx`:
```tsx
export function RecoveryPage() {
  return <div className="p-8 text-2xl font-bold text-gray-900">Recovery Portal — loading...</div>;
}
```

- [ ] **Step 11: Verify frontend builds and runs**

Run:
```bash
cd frontend && npm run dev
```
Expected: Vite dev server starts at `http://localhost:5173`. Visiting `/` shows "OCC Dashboard — loading...". Visiting `/recover/test` shows "Recovery Portal — loading...".

- [ ] **Step 12: Commit**

```bash
git add frontend/
git commit -m "feat: frontend foundation — React + Vite + Tailwind, API client, shared components, routing"
```

---

### Task 9: OCC Dashboard UI — 3-Panel Layout, Disruption Trigger, Passenger Table, KPIs

**Files:**
- Modify: `frontend/src/features/dashboard/DashboardPage.tsx`
- Create: `frontend/src/features/dashboard/DisruptionList.tsx`
- Create: `frontend/src/features/dashboard/PassengerTable.tsx`
- Create: `frontend/src/features/dashboard/ActionPanel.tsx`
- Create: `frontend/src/features/dashboard/TriggerModal.tsx`
- Create: `frontend/src/features/dashboard/PassengerSearch.tsx`

**Interfaces:**
- Consumes: `useDisruptions()`, `usePassengers()`, `useKpis()`, `useFlights()`, `useCreateDisruption()`, `useSendNotifications()`, `useSearchPassengers()` from api hooks in Task 8; `useWebSocket()` from Task 8; `KpiCard`, `StatusBadge` from shared components

- [ ] **Step 1: Create `frontend/src/features/dashboard/TriggerModal.tsx`**

```tsx
import { useState } from "react";
import { useFlights } from "../../api/dashboard";
import { useCreateDisruption } from "../../api/disruptions";

export function TriggerModal({ onClose }: { onClose: () => void }) {
  const { data: flights } = useFlights();
  const mutation = useCreateDisruption();
  const [flight, setFlight] = useState("");
  const [date, setDate] = useState("2027-03-04");
  const [type, setType] = useState("cancellation");
  const [reason, setReason] = useState("technical");

  const submit = () => {
    if (!flight) return;
    mutation.mutate(
      { flight_number: flight, flight_date: date, disruption_type: type, reason },
      { onSuccess: () => onClose() }
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">Trigger Disruption</h2>

        <label className="mb-1 block text-sm font-medium">Flight</label>
        <select
          value={flight}
          onChange={(e) => setFlight(e.target.value)}
          className="mb-3 w-full rounded border p-2 text-sm"
        >
          <option value="">Select flight...</option>
          {flights?.map((f) => (
            <option key={f.flight_number} value={f.flight_number}>
              {f.flight_number} — {f.origin}→{f.destination} ({f.dep_time})
            </option>
          ))}
        </select>

        <label className="mb-1 block text-sm font-medium">Date</label>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="mb-3 w-full rounded border p-2 text-sm"
        />

        <label className="mb-1 block text-sm font-medium">Type</label>
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="mb-3 w-full rounded border p-2 text-sm"
        >
          <option value="cancellation">Cancellation</option>
          <option value="delay">Delay</option>
          <option value="diversion">Diversion</option>
        </select>

        <label className="mb-1 block text-sm font-medium">Reason</label>
        <select
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="mb-3 w-full rounded border p-2 text-sm"
        >
          <option value="technical">Technical</option>
          <option value="weather">Weather</option>
          <option value="atc">ATC</option>
          <option value="crew">Crew</option>
          <option value="other">Other</option>
        </select>

        <div className="mt-4 flex gap-3">
          <button
            onClick={submit}
            disabled={mutation.isPending || !flight}
            className="flex-1 rounded bg-[#CE1126] px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {mutation.isPending ? "Creating..." : "Trigger Disruption"}
          </button>
          <button
            onClick={onClose}
            className="flex-1 rounded border px-4 py-2 text-sm font-medium hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/features/dashboard/DisruptionList.tsx`**

```tsx
import { Disruption } from "../../api/disruptions";

export function DisruptionList({
  disruptions,
  selected,
  onSelect,
}: {
  disruptions: Disruption[];
  selected: number | null;
  onSelect: (id: number) => void;
}) {
  return (
    <div className="space-y-2">
      {disruptions.map((d) => {
        const progress =
          d.affected_pax_count > 0
            ? Math.round((d.recovered_pax_count / d.affected_pax_count) * 100)
            : 0;
        return (
          <button
            key={d.id}
            onClick={() => onSelect(d.id)}
            className={`w-full rounded-lg border-2 p-3 text-left transition ${
              selected === d.id
                ? "border-[#CE1126] bg-red-50"
                : "border-gray-200 bg-white hover:border-gray-300"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-bold">{d.flight_number}</span>
              <span
                className={`rounded px-2 py-0.5 text-xs font-medium ${
                  d.disruption_type === "cancellation"
                    ? "bg-red-100 text-red-700"
                    : d.disruption_type === "delay"
                      ? "bg-yellow-100 text-yellow-700"
                      : "bg-orange-100 text-orange-700"
                }`}
              >
                {d.disruption_type}
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              {d.flight_date} · {d.affected_pax_count} PAX
            </p>
            <div className="mt-2 h-2 w-full rounded-full bg-gray-200">
              <div
                className="h-2 rounded-full bg-green-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-gray-400">
              {d.recovered_pax_count}/{d.affected_pax_count} recovered ({progress}%)
            </p>
          </button>
        );
      })}
      {disruptions.length === 0 && (
        <p className="py-8 text-center text-sm text-gray-400">
          No active disruptions. Click "Trigger Disruption" to start.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/features/dashboard/PassengerTable.tsx`**

```tsx
import { Passenger } from "../../api/disruptions";
import { StatusBadge } from "../shared/StatusBadge";

export function PassengerTable({ passengers }: { passengers: Passenger[] }) {
  return (
    <div className="overflow-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
          <tr>
            <th className="px-3 py-2">Priority</th>
            <th className="px-3 py-2">Name</th>
            <th className="px-3 py-2">PNR</th>
            <th className="px-3 py-2">Tier</th>
            <th className="px-3 py-2">Connection</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Recovery</th>
          </tr>
        </thead>
        <tbody>
          {passengers.map((p) => (
            <tr key={p.id} className="border-b hover:bg-gray-50">
              <td className="px-3 py-2">
                <span
                  className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white ${
                    p.priority_score >= 10
                      ? "bg-red-500"
                      : p.priority_score >= 5
                        ? "bg-orange-500"
                        : "bg-gray-400"
                  }`}
                >
                  {p.priority_score}
                </span>
              </td>
              <td className="px-3 py-2 font-medium">{p.passenger_name}</td>
              <td className="px-3 py-2 font-mono text-xs">{p.pnr}</td>
              <td className="px-3 py-2">{p.loyalty_tier || "—"}</td>
              <td className="px-3 py-2">
                {p.is_misconnect ? (
                  <span className="text-red-600 font-medium">MISCONNECT</span>
                ) : p.is_connecting ? (
                  <span className="text-yellow-600">Connecting</span>
                ) : (
                  <span className="text-gray-400">Direct</span>
                )}
              </td>
              <td className="px-3 py-2">
                <StatusBadge status={p.recovery_status} />
              </td>
              <td className="px-3 py-2 text-xs text-gray-500">
                {p.recovery_flight || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {passengers.length === 0 && (
        <p className="py-8 text-center text-sm text-gray-400">
          Select a disruption to view affected passengers
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/features/dashboard/ActionPanel.tsx`**

```tsx
import { Kpis } from "../../api/dashboard";
import { KpiCard } from "../shared/KpiCard";

export function ActionPanel({
  kpis,
  onNotifyAll,
  isSending,
  notificationResult,
}: {
  kpis: Kpis | undefined;
  onNotifyAll: () => void;
  isSending: boolean;
  notificationResult: { sent_count: number; deep_links: Array<{ pnr: string; deep_link: string }> } | null;
}) {
  return (
    <div className="space-y-4">
      <button
        onClick={onNotifyAll}
        disabled={isSending || !kpis || kpis.pending_count === 0}
        className="w-full rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {isSending ? "Sending..." : `Notify All Pending (${kpis?.pending_count || 0})`}
      </button>

      {notificationResult && notificationResult.sent_count > 0 && (
        <div className="rounded border border-green-200 bg-green-50 p-3">
          <p className="text-sm font-medium text-green-800">
            {notificationResult.sent_count} notifications sent
          </p>
          <div className="mt-2 max-h-40 overflow-auto">
            {notificationResult.deep_links.slice(0, 5).map((l) => (
              <div key={l.pnr} className="mt-1">
                <span className="text-xs font-mono text-gray-600">{l.pnr}: </span>
                <a
                  href={l.deep_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 underline break-all"
                >
                  Open self-service
                </a>
              </div>
            ))}
            {notificationResult.deep_links.length > 5 && (
              <p className="mt-1 text-xs text-gray-400">
                ...and {notificationResult.deep_links.length - 5} more
              </p>
            )}
          </div>
        </div>
      )}

      {kpis && (
        <div className="grid grid-cols-2 gap-3">
          <KpiCard label="Affected" value={kpis.affected_pax_count} />
          <KpiCard
            label="Recovered"
            value={kpis.recovered_pax_count}
            color="text-green-600"
          />
          <KpiCard
            label="Self-Service"
            value={`${kpis.self_service_rate}%`}
            color="text-blue-600"
          />
          <KpiCard label="Pending" value={kpis.pending_count} color="text-orange-600" />
          <KpiCard
            label="Avg Recovery"
            value={
              kpis.avg_recovery_time_seconds
                ? `${Math.round(kpis.avg_recovery_time_seconds / 60)}m`
                : "—"
            }
          />
          <KpiCard
            label="Cost"
            value={`${kpis.total_recovery_cost.toFixed(0)}`}
            unit="AED"
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create `frontend/src/features/dashboard/PassengerSearch.tsx`**

```tsx
import { useState } from "react";
import { useSearchPassengers } from "../../api/disruptions";
import { StatusBadge } from "../shared/StatusBadge";

export function PassengerSearch() {
  const [query, setQuery] = useState("");
  const { data: results } = useSearchPassengers(query);

  return (
    <div className="relative">
      <input
        type="text"
        placeholder="Search by PNR or passenger name..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#CE1126] focus:outline-none focus:ring-1 focus:ring-[#CE1126]"
      />
      {results && results.length > 0 && query.length >= 2 && (
        <div className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md border bg-white shadow-lg">
          {results.map((p) => (
            <div
              key={p.id}
              className="flex items-center justify-between border-b px-3 py-2 text-sm hover:bg-gray-50"
            >
              <div>
                <span className="font-medium">{p.passenger_name}</span>
                <span className="ml-2 font-mono text-xs text-gray-400">{p.pnr}</span>
              </div>
              <StatusBadge status={p.recovery_status} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Wire up `DashboardPage.tsx`**

Replace `frontend/src/features/dashboard/DashboardPage.tsx`:

```tsx
import { useState } from "react";
import { useKpis } from "../../api/dashboard";
import { useDisruptions, usePassengers, useSendNotifications } from "../../api/disruptions";
import { ActionPanel } from "./ActionPanel";
import { DisruptionList } from "./DisruptionList";
import { PassengerSearch } from "./PassengerSearch";
import { PassengerTable } from "./PassengerTable";
import { TriggerModal } from "./TriggerModal";

export function DashboardPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showTrigger, setShowTrigger] = useState(false);
  const [notifResult, setNotifResult] = useState<{
    sent_count: number;
    deep_links: Array<{ pnr: string; deep_link: string }>;
  } | null>(null);

  const { data: disruptions } = useDisruptions();
  const { data: passengers } = usePassengers(selectedId);
  const { data: kpis } = useKpis(selectedId);
  const sendNotifs = useSendNotifications();

  const handleNotify = () => {
    if (!selectedId) return;
    sendNotifs.mutate(selectedId, {
      onSuccess: (data) => setNotifResult(data),
    });
  };

  return (
    <div className="flex h-screen flex-col bg-gray-100">
      {/* Header */}
      <header className="flex items-center justify-between border-b bg-white px-6 py-3 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-[#CE1126]">
            <span className="text-sm font-bold text-white">G9</span>
          </div>
          <h1 className="text-lg font-bold text-gray-900">
            Disruption Management — OCC Dashboard
          </h1>
        </div>
        <div className="w-80">
          <PassengerSearch />
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel */}
        <div className="w-72 shrink-0 overflow-auto border-r bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase text-gray-500">
              Disruptions
            </h2>
            <button
              onClick={() => setShowTrigger(true)}
              className="rounded bg-[#CE1126] px-3 py-1 text-xs font-medium text-white hover:bg-red-700"
            >
              + Trigger
            </button>
          </div>
          <DisruptionList
            disruptions={disruptions || []}
            selected={selectedId}
            onSelect={setSelectedId}
          />
        </div>

        {/* Center Panel */}
        <div className="flex-1 overflow-auto p-4">
          <h2 className="mb-3 text-sm font-bold uppercase text-gray-500">
            Affected Passengers
            {passengers && (
              <span className="ml-2 text-gray-400">({passengers.length})</span>
            )}
          </h2>
          <PassengerTable passengers={passengers || []} />
        </div>

        {/* Right Panel */}
        <div className="w-72 shrink-0 overflow-auto border-l bg-white p-4">
          <h2 className="mb-3 text-sm font-bold uppercase text-gray-500">
            Actions & KPIs
          </h2>
          <ActionPanel
            kpis={kpis}
            onNotifyAll={handleNotify}
            isSending={sendNotifs.isPending}
            notificationResult={notifResult}
          />
        </div>
      </div>

      {showTrigger && <TriggerModal onClose={() => setShowTrigger(false)} />}
    </div>
  );
}
```

- [ ] **Step 7: Verify dashboard renders with backend**

Start backend:
```bash
cd backend && source venv/bin/activate && uvicorn app.main:app --port 8000 --reload &
```

Start frontend:
```bash
cd frontend && npm run dev
```

Visit `http://localhost:5173`. Dashboard should show empty state. Click "Trigger" → select G9001, date 2027-03-04, cancellation → confirm. Dashboard should populate with passengers and KPIs.

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: OCC dashboard — 3-panel layout, disruption trigger, passenger table, KPIs, search"
```

---

### Task 10: Self-Service Portal — Recovery Page, Flight Status, Alternatives, Confirmation

**Files:**
- Modify: `frontend/src/features/self-service/RecoveryPage.tsx`
- Create: `frontend/src/features/self-service/FlightStatus.tsx`
- Create: `frontend/src/features/self-service/AlternativesList.tsx`
- Create: `frontend/src/features/self-service/ConfirmationView.tsx`

**Interfaces:**
- Consumes: `useRecoveryInfo(token)`, `useAcceptOption(token)` from api/recovery in Task 8; `FlightCard` from shared components

- [ ] **Step 1: Create `frontend/src/features/self-service/FlightStatus.tsx`**

```tsx
export function FlightStatus({
  flightNumber,
  segment,
  flightDate,
  disruptionType,
  passengerName,
}: {
  flightNumber: string;
  segment: string | null;
  flightDate: string;
  disruptionType: string;
  passengerName: string | null;
}) {
  const [origin, destination] = (segment || "/").split("/");
  const icon = disruptionType === "cancellation" ? "✕" : "⏱";
  const color =
    disruptionType === "cancellation" ? "text-red-600" : "text-yellow-600";

  return (
    <div className="text-center">
      <div className={`mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-3xl ${color}`}>
        {icon}
      </div>
      {passengerName && (
        <p className="mb-2 text-sm text-gray-500">Hello, {passengerName}</p>
      )}
      <h2 className="text-xl font-bold text-gray-900">
        Flight {flightNumber} has been {disruptionType === "cancellation" ? "cancelled" : "delayed"}
      </h2>
      <p className="mt-2 text-gray-600">
        {origin} → {destination} on {flightDate}
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/features/self-service/AlternativesList.tsx`**

```tsx
import { RecoveryOption } from "../../api/recovery";
import { FlightCard } from "../shared/FlightCard";

export function AlternativesList({
  options,
  onSelect,
  onRefund,
  isLoading,
}: {
  options: RecoveryOption[];
  onSelect: (optionId: number) => void;
  onRefund: () => void;
  isLoading: boolean;
}) {
  return (
    <div>
      <h3 className="mb-4 text-lg font-bold text-gray-900">
        Alternative Flights Available
      </h3>
      <div className="space-y-3">
        {options.map((opt) => (
          <FlightCard
            key={opt.id}
            flightNumber={opt.flight_number}
            origin={opt.origin || ""}
            destination={opt.destination || ""}
            depTime={opt.departure_time || ""}
            arrTime={opt.arrival_time || ""}
            seats={opt.available_seats}
            fareDiff={opt.fare_difference}
            onSelect={() => onSelect(opt.id)}
          />
        ))}
      </div>

      <div className="mt-6 border-t pt-4">
        <button
          onClick={onRefund}
          disabled={isLoading}
          className="w-full rounded-md border-2 border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Request Full Refund Instead
        </button>
      </div>

      <p className="mt-4 text-center text-xs text-gray-400">
        Need help? Contact Air Arabia support
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/features/self-service/ConfirmationView.tsx`**

```tsx
export function ConfirmationView({
  flightNumber,
  departureTime,
  status,
}: {
  flightNumber?: string;
  departureTime?: string;
  status: string;
}) {
  const isRefund = status === "refunded";

  return (
    <div className="text-center">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-3xl text-green-600">
        ✓
      </div>
      {isRefund ? (
        <>
          <h2 className="text-xl font-bold text-gray-900">
            Refund Request Submitted
          </h2>
          <p className="mt-2 text-gray-600">
            Your refund will be processed within 7-14 business days.
          </p>
        </>
      ) : (
        <>
          <h2 className="text-xl font-bold text-gray-900">
            You're Confirmed on {flightNumber}
          </h2>
          <p className="mt-2 text-gray-600">
            New departure: {departureTime}
          </p>
          <p className="mt-1 text-sm text-gray-400">
            A confirmation email has been sent.
          </p>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Wire up `RecoveryPage.tsx`**

Replace `frontend/src/features/self-service/RecoveryPage.tsx`:

```tsx
import { useState } from "react";
import { useParams } from "react-router-dom";
import { useAcceptOption, useRecoveryInfo } from "../../api/recovery";
import { AlternativesList } from "./AlternativesList";
import { ConfirmationView } from "./ConfirmationView";
import { FlightStatus } from "./FlightStatus";

export function RecoveryPage() {
  const { token } = useParams<{ token: string }>();
  const { data: info, isLoading, error, refetch } = useRecoveryInfo(token);
  const accept = useAcceptOption(token);
  const [confirmed, setConfirmed] = useState<{
    flight?: string;
    time?: string;
    status: string;
  } | null>(null);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-gray-500">Loading your recovery options...</p>
      </div>
    );
  }

  if (error || !info) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-lg font-medium text-red-600">
            Invalid or expired recovery link
          </p>
          <p className="mt-2 text-sm text-gray-500">
            Please contact Air Arabia support for assistance.
          </p>
        </div>
      </div>
    );
  }

  const isResolved = ["self_served", "refunded"].includes(info.recovery_status) || confirmed;

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="mb-6 text-center">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded bg-[#CE1126]">
            <span className="text-sm font-bold text-white">G9</span>
          </div>
          <p className="mt-1 text-xs text-gray-400">Air Arabia</p>
        </div>

        <div className="rounded-xl bg-white p-6 shadow-lg">
          {isResolved ? (
            <ConfirmationView
              flightNumber={confirmed?.flight || info.options.find(o => o.status === "accepted")?.flight_number}
              departureTime={confirmed?.time || info.options.find(o => o.status === "accepted")?.departure_time || undefined}
              status={confirmed?.status || info.recovery_status}
            />
          ) : (
            <>
              <FlightStatus
                flightNumber={info.flight_number}
                segment={info.original_segment}
                flightDate={info.flight_date}
                disruptionType={info.disruption_type}
                passengerName={info.passenger_name}
              />

              <div className="my-6 border-t" />

              <AlternativesList
                options={info.options}
                isLoading={accept.isPending}
                onSelect={(optionId) => {
                  accept.mutate(
                    { option_id: optionId, action: "accept" },
                    {
                      onSuccess: (data: any) => {
                        setConfirmed({
                          flight: data.flight_number,
                          time: data.departure_time,
                          status: "self_served",
                        });
                      },
                    }
                  );
                }}
                onRefund={() => {
                  accept.mutate(
                    { action: "refund" },
                    {
                      onSuccess: () => {
                        setConfirmed({ status: "refunded" });
                      },
                    }
                  );
                }}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify self-service portal end-to-end**

1. Start backend + frontend
2. On dashboard, trigger disruption for G9001
3. Click "Notify All Pending"
4. Copy a deep link from the notification result
5. Open in a new tab → should show cancellation notice + alternative flights
6. Click "Select This Flight" → should show confirmation
7. Check OCC dashboard → passenger status should update to "self_served"

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: self-service portal — flight status, alternatives, acceptance, refund, confirmation"
```

---

### Task 11: End-to-End Integration & Demo Validation

**Files:**
- Create: `backend/tests/test_e2e.py`
- Possibly modify: any file with bugs found during validation

**Interfaces:**
- Consumes: entire backend API surface from Tasks 3–7
- Produces: validated, working demo

- [ ] **Step 1: Write end-to-end test**

Create `backend/tests/test_e2e.py`:

```python
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200


def test_flights_loaded():
    r = client.get("/api/dashboard/flights")
    assert r.status_code == 200
    flights = r.json()
    assert len(flights) > 0
    numbers = [f["flight_number"] for f in flights]
    assert "G9001" in numbers


def test_full_disruption_flow():
    r = client.post("/api/disruptions", json={
        "flight_number": "G9001",
        "flight_date": "2027-03-04",
        "disruption_type": "cancellation",
        "reason": "technical",
    })
    assert r.status_code == 200
    disruption = r.json()
    d_id = disruption["id"]
    assert disruption["affected_pax_count"] > 0

    r = client.get(f"/api/disruptions/{d_id}/passengers")
    assert r.status_code == 200
    passengers = r.json()
    assert len(passengers) > 0
    assert all(p["recovery_status"] == "pending" for p in passengers)

    r = client.get(f"/api/dashboard/kpis?disruption_id={d_id}")
    assert r.status_code == 200
    kpis = r.json()
    assert kpis["affected_pax_count"] == len(passengers)
    assert kpis["pending_count"] == len(passengers)

    r = client.post(f"/api/notifications/{d_id}/send")
    assert r.status_code == 200
    notif = r.json()
    assert notif["sent_count"] > 0
    assert len(notif["deep_links"]) > 0

    deep_link = notif["deep_links"][0]["deep_link"]
    token = deep_link.split("/recover/")[1]

    r = client.get(f"/api/recovery/{token}")
    assert r.status_code == 200
    recovery = r.json()
    assert recovery["disruption_type"] == "cancellation"
    assert len(recovery["options"]) > 0

    option_id = recovery["options"][0]["id"]
    r = client.post(f"/api/recovery/{token}/accept", json={
        "option_id": option_id,
        "action": "accept",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    r = client.get(f"/api/disruptions/{d_id}/passengers")
    pax_list = r.json()
    pnr = notif["deep_links"][0]["pnr"]
    pax = next((p for p in pax_list if p["pnr"] == pnr), None)
    assert pax is not None
    assert pax["recovery_status"] == "self_served"

    r = client.get(f"/api/dashboard/kpis?disruption_id={d_id}")
    kpis = r.json()
    assert kpis["recovered_pax_count"] >= 1
    assert kpis["self_service_rate"] > 0
```

- [ ] **Step 2: Run end-to-end test**

Run:
```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_e2e.py -v
```
Expected: All assertions pass — complete flow from disruption creation through self-service acceptance.

- [ ] **Step 3: Run all tests together**

Run:
```bash
cd backend && source venv/bin/activate && python -m pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 4: Manual demo walkthrough**

1. Delete `backend/disruption.db` to get fresh data
2. Start backend: `cd backend && uvicorn app.main:app --port 8000 --reload`
3. Start frontend: `cd frontend && npm run dev`
4. Open `http://localhost:5173` — OCC Dashboard loads
5. Click "Trigger" → G9001, 2027-03-04, cancellation, technical → Submit
6. Watch left panel: disruption card appears with PAX count
7. Watch center panel: passenger table fills with priority-scored passengers
8. Watch right panel: KPIs show affected count
9. Click "Notify All Pending" → notification count updates, deep links appear
10. Copy first deep link → open in new incognito tab (mobile viewport)
11. See: cancellation notice, alternative flights, select one → confirmation
12. Return to OCC dashboard → passenger status updated to "self_served", KPIs update

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_e2e.py
git commit -m "test: end-to-end integration test — full disruption recovery pipeline"
```

---

## Appendix: File Inventory

| Path | Purpose |
|---|---|
| `backend/requirements.txt` | Python dependencies |
| `backend/app/main.py` | FastAPI app, CORS, WebSocket, router registration |
| `backend/app/database.py` | SQLAlchemy engine, session, Base |
| `backend/app/core/config.py` | Settings from env vars |
| `backend/app/core/security.py` | JWT create/decode |
| `backend/app/core/websocket.py` | WebSocket connection manager |
| `backend/app/models/*.py` | 7 ORM model files (10 tables total) |
| `backend/app/data_loader/loader.py` | ETL from CSV/Excel/Zip → SQLite |
| `backend/app/modules/disruption/` | Disruption event CRUD + pipeline orchestration |
| `backend/app/modules/passenger/` | Impact analysis, misconnect detection, priority scoring |
| `backend/app/modules/recovery/` | Alternative generation, acceptance, refund |
| `backend/app/modules/notification/` | JWT deep links, email simulation |
| `backend/app/modules/dashboard/` | KPIs, flights list |
| `backend/tests/` | 6 test files |
| `frontend/src/App.tsx` | React router setup |
| `frontend/src/api/*.ts` | 4 API client files with TanStack Query hooks |
| `frontend/src/hooks/useWebSocket.ts` | Dashboard real-time updates |
| `frontend/src/features/dashboard/*.tsx` | 6 dashboard components |
| `frontend/src/features/self-service/*.tsx` | 4 self-service components |
| `frontend/src/features/shared/*.tsx` | 3 shared components |
