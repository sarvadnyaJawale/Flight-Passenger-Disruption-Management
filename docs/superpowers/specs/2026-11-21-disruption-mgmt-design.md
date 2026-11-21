# Flight & Passenger Disruption Management Platform — Design Spec

**Date**: 2026-11-21
**Context**: Air Arabia hackathon — one-day build
**Approach**: Reuse proven industry patterns from Amadeus Passenger Recovery, Plan3, 15below, WNS RePAX

---

## 1. Problem Statement

Flight disruptions cost the airline industry ~$60B annually. Manual rebooking of a full flight takes 3–4 hours (pre-automation benchmark from SWISS). Air Arabia operates 383 flights across 88 stations from multiple hubs (SHJ, AUH, Morocco, Egypt, Pakistan) with ~100 A320-family aircraft and high seat-load factors.

The platform automates the end-to-end disruption recovery flow: detect → identify affected passengers → generate alternatives → notify → enable self-service → track recovery — matching the capabilities that delivered SWISS's 2–3 minute recovery, Air Canada's 90% automation rate, and PLAY's 80%+ self-service uptake.

## 2. Architecture

### 2.1 Approach: Monolith with Feature Modules

Single FastAPI backend + React SPA frontend. Clean module boundaries per feature domain. Shared PostgreSQL database.

This mirrors how Plan3 and 15below operate — focused overlays with clean internal separation, not microservices.

```
┌─────────────────────────────────────────────────────────┐
│                     React + Vite + Tailwind              │
│  ┌──────────────────┐    ┌────────────────────────────┐  │
│  │  OCC Dashboard   │    │  Passenger Self-Service     │  │
│  │  /dashboard      │    │  /recover/{token}           │  │
│  └───────┬──────────┘    └────────────┬───────────────┘  │
│          │  REST + WebSocket          │  REST             │
└──────────┼────────────────────────────┼──────────────────┘
           │                            │
┌──────────┼────────────────────────────┼──────────────────┐
│          ▼         FastAPI            ▼                   │
│  ┌────────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ │
│  │ disruption │ │passenger │ │ recovery  │ │notific.  │ │
│  │  module    │ │ module   │ │  module   │ │ module   │ │
│  └─────┬──────┘ └────┬─────┘ └─────┬─────┘ └────┬─────┘ │
│        │             │             │             │        │
│  ┌─────┴─────────────┴─────────────┴─────────────┴─────┐ │
│  │              dashboard module (KPIs, WS)             │ │
│  └──────────────────────┬──────────────────────────────┘ │
└─────────────────────────┼────────────────────────────────┘
                          │
                ┌─────────▼─────────┐
                │   PostgreSQL      │
                │   (SQLite for     │
                │    hackathon)     │
                └───────────────────┘
```

### 2.2 Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend | Python 3.11+ / FastAPI / Pydantic / SQLAlchemy | Fast API dev, strong validation, async support |
| Database | SQLite (hackathon) — schema is PostgreSQL-compatible for production | Zero infrastructure, single file, fast setup. Load a demo subset of booking data. |
| Frontend | React 18 + Vite + Tailwind CSS + shadcn/ui | Component-based, fast styling, production-quality UI |
| Data fetching | TanStack Query | Caching, background refetching, loading states |
| Real-time | WebSocket (FastAPI native) | Live dashboard updates as PAX self-serve |
| Notifications | Resend (email, free tier) + console SMS simulation | Minimal setup, real emails for demo |
| Auth | JWT tokens (simple, no Supabase Auth for hackathon speed) | PNR-based access tokens for self-service portal |

### 2.3 Project Structure

```
backend/
  app/
    main.py                 # FastAPI app, CORS, WebSocket
    database.py             # SQLAlchemy engine, session, Base
    models/                 # SQLAlchemy ORM models
      flight.py             # Flight, FlightInstance, FlightInventory
      booking.py            # Booking, Passenger
      disruption.py         # Disruption, DisruptionPassenger
      recovery.py           # RecoveryOption, RecoveryCost
      connection.py         # ConnectionRule
      loyalty.py            # LoyaltyMember
      audit.py              # AuditLog
    modules/
      disruption/
        router.py           # POST /api/disruptions, GET ...
        service.py          # create_disruption, trigger pipeline
        schemas.py          # Pydantic request/response models
      passenger/
        router.py           # GET /api/disruptions/{id}/passengers
        service.py          # identify_affected, detect_misconnects, score_priority
        schemas.py
      recovery/
        router.py           # GET .../alternatives, POST /api/recovery/accept
        service.py          # generate_alternatives, accept_alternative, process_refund
        schemas.py
      notification/
        router.py           # POST /api/notifications/send
        service.py          # send_notifications, generate_deep_links
        schemas.py
      dashboard/
        router.py           # GET /api/dashboard/*, WebSocket /ws/dashboard
        service.py          # aggregate_kpis, get_active_disruptions
        schemas.py
    data_loader/
      loader.py             # ETL: CSV/Excel → database tables
      parsers.py            # File-specific parsing logic
    core/
      config.py             # Settings (env vars)
      security.py           # JWT token creation/validation
      websocket.py          # Connection manager

frontend/
  src/
    App.tsx
    features/
      dashboard/
        DashboardPage.tsx       # Main OCC 3-panel layout
        DisruptionList.tsx       # Left panel: active disruptions
        PassengerTable.tsx       # Center: affected PAX table
        ActionPanel.tsx          # Right: actions + KPI cards
        PassengerSearch.tsx      # Search by PNR or name
      self-service/
        RecoveryPage.tsx         # /recover/{token} entry
        FlightStatus.tsx         # Cancellation notice
        AlternativesList.tsx     # Available options
        ConfirmationView.tsx     # Booking confirmed
      shared/
        KpiCard.tsx
        StatusBadge.tsx
        FlightCard.tsx
    api/
      client.ts                 # Axios/fetch wrapper
      disruptions.ts            # API hooks (TanStack Query)
      recovery.ts
      dashboard.ts
    hooks/
      useWebSocket.ts           # Dashboard real-time updates
```

## 3. Data Model

All tables mapped directly from Air Arabia data files.

### 3.1 Core Tables

**flights** (from Flight Schedule.csv — 6,143 records, 383 unique flights)
```
flight_number       VARCHAR     PK (composite with schedule dates)
origin              VARCHAR(3)  IATA code
destination         VARCHAR(3)  IATA code
dep_time_local      TIME
arr_time_local      TIME
frequency           VARCHAR     "MON:TUE:WED:..."
schedule_start      DATE
schedule_end        DATE
```

**flight_instances** (from Flight Punctuality — 65,943 records)
```
id                  SERIAL      PK
flight_number       VARCHAR     FK → flights
date                DATE
aircraft_reg        VARCHAR     e.g., A6-ANB
std                 TIMESTAMP   Scheduled departure
atd                 TIMESTAMP   Actual departure (nullable)
sta                 TIMESTAMP   Scheduled arrival
ata                 TIMESTAMP   Actual arrival (nullable)
dep_delay_mins      INTEGER
arr_delay_mins      INTEGER
delay_code          VARCHAR     e.g., "5min-71A"
pax_count           INTEGER
status              ENUM        scheduled/delayed/cancelled/diverted
diversion_airport   VARCHAR(3)  nullable
```

**flight_inventory** (from Flight Inventory.csv — 368,874 records)
```
id                  SERIAL      PK
flight_number       VARCHAR
departure_datetime  TIMESTAMP
aircraft_model      VARCHAR     e.g., A320-174
adult_capacity      INTEGER     174 or 162
booking_class       VARCHAR     e.g., E28, E70
allocated_seats     INTEGER
available_seats     INTEGER
```

**bookings** (from Booking Data — multi-month, ~877MB total)
```
id                  SERIAL      PK
pnr                 VARCHAR     e.g., 6KPJ6R
booking_timestamp   TIMESTAMP
sales_channel       VARCHAR     TravelAgent/Web/Mobile
res_status          VARCHAR     HK/CNX/etc.
is_lms_member       BOOLEAN
pax_type            VARCHAR     Adult/Child/Infant
first_name          VARCHAR
last_name           VARCHAR
flight_number       VARCHAR
departure_zulu      TIMESTAMP
segment_code        VARCHAR     "SHJ/JED" — origin/destination
flight_status       VARCHAR
booking_class       VARCHAR
pax_status          VARCHAR
total_fare          DECIMAL
total_surcharges    DECIMAL
total_taxes         DECIMAL
baggage_weight      INTEGER
meals               VARCHAR
seat_code           VARCHAR
-- Mock fields for demo:
email               VARCHAR     generated
phone               VARCHAR     generated
```

**connection_rules** (from Connection Time.xlsx — 40 records)
```
ond_code            VARCHAR     PK  e.g., "ALY/SHJ/SLL"
origin              VARCHAR(3)  parsed from ond_code
hub                 VARCHAR(3)  parsed (always SHJ in current data)
destination         VARCHAR(3)  parsed from ond_code
min_conn_time_mins  INTEGER     55
max_conn_time_mins  INTEGER     1200
status              VARCHAR     ACT/INACT
```

**loyalty** (from Loyalty_Sample Data.xlsx — 15 records)
```
loyalty_id          VARCHAR     PK (email)
pax_type            VARCHAR
pax_name            VARCHAR
family_or_ind       VARCHAR     Family/Individual
head_of_family      BOOLEAN
tier                VARCHAR     Basic/Silver/Gold
available_points    INTEGER
```

### 3.2 Platform Tables (created by the system)

**disruptions**
```
id                  SERIAL      PK
flight_number       VARCHAR
flight_date         DATE
disruption_type     ENUM        cancellation/delay/diversion
reason              VARCHAR     weather/technical/atc/crew/other
created_at          TIMESTAMP
created_by          VARCHAR     operator username
status              ENUM        active/resolved
affected_pax_count  INTEGER     computed
recovered_pax_count INTEGER     computed
```

**disruption_passengers**
```
id                  SERIAL      PK
disruption_id       INTEGER     FK → disruptions
pnr                 VARCHAR
passenger_name      VARCHAR
is_connecting       BOOLEAN
is_misconnect       BOOLEAN
connecting_flight   VARCHAR     nullable
priority_score      INTEGER     computed
recovery_status     ENUM        pending/notified/options_viewed/self_served/manually_handled/refunded
recovery_flight     VARCHAR     nullable (the alternative accepted)
notified_at         TIMESTAMP   nullable
recovered_at        TIMESTAMP   nullable
```

**recovery_options** (generated alternatives)
```
id                  SERIAL      PK
disruption_id       INTEGER     FK → disruptions
pnr                 VARCHAR
flight_number       VARCHAR     alternative flight
departure_time      TIMESTAMP
available_seats     INTEGER
fare_difference     DECIMAL
rank                INTEGER     1 = best option
status              ENUM        offered/accepted/declined/expired
```

**recovery_costs**
```
id                  SERIAL      PK
disruption_id       INTEGER     FK → disruptions
pnr                 VARCHAR
cost_type           ENUM        rebooking_fare_diff/hotel/meal/transport/compensation
amount              DECIMAL
currency            VARCHAR     default AED
created_at          TIMESTAMP
```

**audit_log**
```
id                  SERIAL      PK
disruption_id       INTEGER     FK → disruptions (nullable)
pnr                 VARCHAR     nullable
action              VARCHAR     disruption_created/pax_identified/notification_sent/
                                alternative_offered/alternative_accepted/refund_requested/
                                manual_override
details             JSONB
actor               ENUM        system/operator/passenger
created_at          TIMESTAMP
```

## 4. Module Details

### 4.1 Disruption Module

**Purpose**: Create and manage disruption events. Entry point for the entire recovery pipeline.

**Key endpoint**: `POST /api/disruptions`
```json
{
  "flight_number": "G9001",
  "flight_date": "2026-11-22",
  "disruption_type": "cancellation",
  "reason": "technical"
}
```

**Pipeline trigger**: On creation, the service:
1. Creates disruption record
2. Calls `passenger.service.identify_affected(disruption_id)`
3. Calls `recovery.service.generate_alternatives(disruption_id)`
4. Broadcasts update via WebSocket to connected dashboards
5. Logs to audit_log

### 4.2 Passenger Module

**Purpose**: Identify affected passengers and assess impact.

**identify_affected(disruption_id)**:
1. Query bookings where `flight_number` = disrupted flight AND `departure_zulu` matches date AND `res_status` = active
2. For each passenger, check if they have another segment on the same PNR
3. If connecting: parse `segment_code`, find the connecting flight's departure time, compare with `arrival_time + min_conn_time` from connection_rules
4. Flag as `is_misconnect` if connection is broken

**score_priority(passenger)**:
```python
score = 0
# Loyalty tier (from loyalty table join on name/email)
if tier == "Gold": score += 5
elif tier == "Silver": score += 3
elif tier == "Basic": score += 1

# Connection criticality
if is_misconnect: score += 5
elif is_connecting: score += 2

# Family/group
if head_of_family: score += 2
if pax_type == "Child": score += 3  # children need priority handling

# Commercial value (fare-based)
if total_fare > high_value_threshold: score += 2
```
Source: Amadeus and Sabre both support loyalty + SSR + connection-based prioritization.

### 4.3 Recovery Module

**Purpose**: Generate and manage rebooking alternatives.

**generate_alternatives(disruption_id, pnr)**:
1. Get original flight's origin + destination from booking's `segment_code`
2. Query `flights` for same O&D within next 24 hours
3. For each candidate, check `flight_inventory` for `available_seats > 0`
4. Calculate fare difference: `candidate_fare - original_fare`
5. Rank: (1) earliest departure, (2) lowest fare difference, (3) direct preferred
6. Store top 3 as `recovery_options`
7. Always include refund option

**accept_alternative(pnr, option_id)**:
1. Update `recovery_options.status` = accepted
2. Decrement `flight_inventory.available_seats` for the selected flight
3. Update `disruption_passengers.recovery_status` = self_served
4. Update `disruption_passengers.recovery_flight` = selected flight
5. Log fare difference to `recovery_costs`
6. Broadcast via WebSocket
7. Audit log entry

### 4.4 Notification Module

**Purpose**: Send multi-channel notifications with deep links.

**send_notifications(disruption_id)**:
1. Get all `disruption_passengers` with status = pending
2. For each, generate JWT token encoding PNR + disruption_id (expires 24h)
3. Build deep link: `{BASE_URL}/recover/{token}`
4. Send email via Resend API (or log to console in dev mode):
   ```
   Subject: Flight G9001 Update — Action Required
   Body: Your flight G9001 from Sharjah to Jeddah on Nov 22 has been cancelled.
         We have found {n} alternative flights for you.
         [View Your Options →] {deep_link}
   ```
5. Update `disruption_passengers.notified_at` = now
6. Update `disruption_passengers.recovery_status` = notified
7. Broadcast via WebSocket
8. Audit log per notification

Source: 15below pattern — personalized, action-linked notifications.

### 4.5 Dashboard Module

**Purpose**: Real-time OCC view + KPI aggregation.

**KPIs computed from database**:
- `affected_pax_count`: COUNT of disruption_passengers for active disruptions
- `recovered_pax_count`: COUNT WHERE recovery_status IN (self_served, manually_handled)
- `self_service_rate`: recovered_via_self_service / total_recovered × 100
- `avg_notification_time`: AVG(notified_at - disruption.created_at)
- `avg_recovery_time`: AVG(recovered_at - disruption.created_at)
- `total_recovery_cost`: SUM(recovery_costs.amount) per disruption
- `exception_count`: COUNT WHERE recovery_status = pending AND notified_at > 30 min ago

**WebSocket /ws/dashboard**:
- Pushes events: `disruption_created`, `passenger_identified`, `notification_sent`, `passenger_self_served`, `kpi_updated`
- OCC dashboard subscribes on page load, updates UI in real-time

**Passenger search**: `GET /api/dashboard/search?q={pnr_or_name}`
- Searches disruption_passengers by PNR (exact) or name (ILIKE)
- Returns full passenger recovery details

## 5. Frontend Details

### 5.1 OCC Dashboard (/dashboard)

Three-panel layout:

**Left Panel — Disruption List**
- Card per active disruption: flight number, route, type badge (cancelled/delayed), affected count, progress bar
- "Trigger Disruption" button opens modal: select flight, type, reason → POST /api/disruptions
- Click a disruption → loads its passengers in center panel

**Top Bar — Search**
- Search input: "Search by PNR or passenger name..."
- Results dropdown → click to open passenger detail

**Center Panel — Passenger Table**
- Sortable columns: Priority Score, Name, PNR, Loyalty Tier, Connection Status, Recovery Status
- Status badges: pending (gray), notified (blue), options_viewed (yellow), self_served (green), refunded (purple), manually_handled (orange)
- Row click → expand to show offered alternatives and selected option

**Right Panel — Actions & KPIs**
- "Notify All Pending" button → POST /api/notifications/send
- "Auto-Recover Top Priority" → batch accept best alternative for top-N
- KPI cards: 5 cards showing real-time metrics (see Section 4.5)
- Recovery cost breakdown: pie chart of cost types

### 5.2 Passenger Self-Service Portal (/recover/{token})

Mobile-first, minimal design. Air Arabia brand (red #CE1126, white, dark gray).

**Step 1 — Flight Status**
- Large icon (cancelled/delayed)
- "Your flight G9001 from Sharjah (SHJ) to Jeddah (JED) on November 22, 2026 has been cancelled."
- "We've found alternative options for you:"

**Step 2 — Alternatives**
- 2-3 flight cards: flight number, departure time, arrival time, seats available, fare difference
- Each card has "Select This Flight" button
- "Request Full Refund" button at bottom
- "Need Help? Contact Support" link

**Step 3 — Confirmation**
- "You're confirmed on flight G9003"
- New departure: 13:00, Arrival: 14:50
- "A confirmation email has been sent."

### 5.3 Shared Components
- `KpiCard` — metric label + value + trend indicator
- `StatusBadge` — colored badge for recovery status
- `FlightCard` — flight number, route, times, availability
- `PriorityBadge` — color-coded priority score

## 6. Data Loading (ETL)

### 6.1 Strategy
Pre-load data at application startup or via a CLI command (`python -m app.data_loader.loader`).

### 6.2 File → Table Mapping

| File | Target Table | Records | Notes |
|---|---|---|---|
| Flight Schedule.csv | flights | 6,143 | Direct column mapping |
| Flight Inventory.csv | flight_inventory | 368,874 | Direct column mapping |
| Flight_Punctuality*.xlsx | flight_instances | 65,943 | Parse delay codes, compute status |
| Flight Rotation.xls | flight_instances | 4,646 | Merge with punctuality (same schema) |
| Connection Time.xlsx | connection_rules | 40 | Parse ond_code into origin/hub/dest |
| Loyalty_Sample Data.xlsx | loyalty | 15 | Direct mapping |
| Booking Data (zip) | bookings | ~50K subset | Extract one month, generate mock email/phone |

### 6.3 Mock Data Generation
- **Contact info**: For each unique PNR, generate: `{first_name.lower()}.{last_name.lower()}@example.com` and a mock phone `+971-50-XXX-XXXX`
- **Demo subset**: Load only bookings for flights G9001–G9020 on a single date to keep demo responsive

## 7. Demo Scenario

### Trigger
OCC operator cancels flight G9001 (SHJ→JED, 09:00, 174 capacity, A320-174)

### Expected Outcomes
1. ~150 affected passengers identified from booking data
2. ~12 misconnecting passengers flagged (JED connections to MED, RUH, etc.)
3. 3 high-priority passengers identified (Silver loyalty, families)
4. 2–3 alternative flights found with available seats from inventory
5. Notifications sent to all 150 passengers (<1 minute)
6. Self-service portal accessible via deep link
7. Dashboard shows live recovery progress
8. KPIs: self-service rate trending toward 80%+, avg recovery time <5 min

### Industry Benchmarks (for pitch comparison)
- SWISS pre-automation: 3–4 hours → Post: 2–3 minutes
- Air Canada: 90% automated, 10-minute average, 11,500 PAX in one event
- PLAY (Plan3): >80% self-service
- 15below: 225,000 notifications in 24 hours during Polar Vortex
- WNS RePAX: 180-pax flight from 4–5 hours → 45 minutes

## 8. Data Gaps

| Missing Data | Impact | Mitigation |
|---|---|---|
| Passenger contact info (email/phone) | Cannot send real notifications | Generate mock contacts from PNR names |
| Hotel/ground transport suppliers | Cannot offer care packages | Defer to Should-Have; show placeholder UI |
| Real-time flight status feed | No live ATC/weather data | Use pre-loaded data; demo via manual trigger |
| Crew/aircraft constraints | Cannot validate aircraft swap | Out of scope for hackathon |

## 9. Security

- PNR access via JWT tokens (24h expiry, encodes PNR + disruption_id)
- No real passenger PII in demo — names from data, mock contacts
- CORS restricted to frontend origin
- No authentication for OCC dashboard in hackathon (would add Supabase Auth in production)

## 10. Testing Plan

- **Data loader**: Verify all CSVs/Excel files load without errors, correct row counts
- **Disruption trigger**: Cancel a flight → verify correct PAX count identified
- **Misconnect detection**: Verify connecting passengers flagged based on connection_rules
- **Alternative generation**: Verify only flights with available_seats > 0 are offered
- **Self-service flow**: Accept alternative → verify inventory decremented, status updated
- **WebSocket**: Dashboard updates in real-time when PAX self-serves
- **KPIs**: Verify calculations match expected values

## 11. Out of Scope (Deferred)

- Predictive disruption alerts (ML on punctuality data)
- Crew & aircraft recovery linkage
- Interline / partner carrier rebooking
- Hotel/meal/ground transport packages (UI placeholder only)
- Agentic AI orchestration
- Production authentication & authorization
- Multi-language support
- Payment processing for fare differences
