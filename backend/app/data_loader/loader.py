import csv
import hashlib
import io
import os
import zipfile
from datetime import datetime

import openpyxl

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
            fn = row["flight_number"]
            if not fn:
                continue
            inv = FlightInventory(
                flight_number=fn,
                departure_datetime_local=row["departure_date_time_local"],
                departure_datetime_zulu=row["departure_date_time_zulu"],
                aircraft_model=row["aircraft_model"],
                adult_capacity=int(row["adult_capacity"] or 0),
                booking_class=row["bc_code"],
                allocated_seats=int(row["allocated_seats"] or 0),
                available_seats=int(row["available_seats"] or 0),
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
    if not name or name == ".":
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
                        reader = csv.DictReader(io.TextIOWrapper(cf, "utf-8", errors="replace"))
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
        print(f"  -> {n} flight schedule records")

        print("Loading flight inventory...")
        n = load_inventory(session, data_dir)
        print(f"  -> {n} inventory records")

        print("Loading booking data (demo flights only)...")
        n = load_bookings(session, data_dir, target_flights=DEMO_FLIGHTS)
        print(f"  -> {n} booking records")

        print("Loading connection rules...")
        n = load_connections(session, data_dir)
        print(f"  -> {n} connection rules")

        print("Loading loyalty data...")
        n = load_loyalty(session, data_dir)
        print(f"  -> {n} loyalty members")

        print("ETL complete.")
    finally:
        session.close()


if __name__ == "__main__":
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "../data"
    load_all(data_dir)
