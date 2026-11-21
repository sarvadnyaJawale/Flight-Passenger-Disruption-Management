# Airline Resilience OS — Phase 1: Flight & Passenger Disruption Management

> An intelligent disruption recovery platform that transforms reactive crisis response into proactive, cost-optimised passenger care.

## The Vision: Airline Resilience OS

This is **Phase 1** of a modular Airline Resilience Operating System — a platform that grows from disruption management into a full operational intelligence layer for airline operations.

| Phase | Capability | Status |
|-------|-----------|--------|
| **1 — Disruption Recovery** | Real-time PAX recovery, cost modelling, cascade analysis | **Now** |
| 2 — Predictive Intelligence | ML-driven delay forecasting, proactive rebooking | Planned |
| 3 — Revenue Protection | Dynamic fare optimisation during IRROPS, ancillary recovery | Planned |
| 4 — Ops Integration | Crew rotation, maintenance slot awareness, ATC feed ingestion | Planned |

## What Phase 1 Delivers

### Economic Decision Engine
- **Cost-per-passenger breakdown** — hotel (AED 350), meals (AED 50), compensation with loyalty/connecting bonuses
- **"Do Nothing" baseline** — EU261/UAE liability projection vs. recovery cost, showing judges the savings
- **Parallel recovery strategies** — cheapest, fastest, and best-experience ranked side by side

### Cascade Visibility
- **Downstream impact analysis** — which flights lose their aircraft when one is cancelled
- **Route-based rotation detection** — automatic identification of affected departures

### Recovery Orchestration
- **Automated alternative search** — finds rebooking options across the schedule
- **Priority scoring** — connecting PAX, loyalty tier, fare value drive recovery order
- **Multi-channel notification** — email/SMS/push via Novu integration

### OCC Dashboard
- **Single-pane-of-glass** — KPIs, cost breakdown, baseline comparison, strategy cards, cascade warnings
- **Real-time WebSocket updates** — live status changes as PAX are recovered
- **One-click disruption trigger** — simulate cancellation for demo

## Architecture

```
┌────────────────────────────────────────────────────┐
│                 React 19 + Vite 8                  │
│         shadcn/ui · TanStack Query 5               │
│          Tailwind 4 · WebSocket live               │
├────────────────────────────────────────────────────┤
│              FastAPI 0.115 (Python)                │
│    6 modules: disruption · passenger · recovery    │
│              notification · dashboard · cost       │
├────────────────────────────────────────────────────┤
│           TimescaleDB (PostgreSQL 16)              │
│       Time-series ready for Phase 2 ML             │
└────────────────────────────────────────────────────┘
```

## Quick Start

```bash
docker compose up
```

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Project Structure

```
backend/
  app/
    modules/
      disruption/    — flight cancellation events
      passenger/     — PAX records, priority scoring
      recovery/      — alternative search, rebooking
      notification/  — multi-channel alerts via Novu
      dashboard/     — KPI aggregation, WebSocket
      cost/          — economic analysis engine
  tests/             — 25 tests, TDD-driven
frontend/
  src/
    features/
      dashboard/     — OCC command centre
    api/             — typed API client layer
    components/ui/   — shadcn/ui component library
```

## Why This Wins

1. **Economic Intelligence** — not just recovery, but cost justification with AED figures judges can verify
2. **Cascade Awareness** — competitors treat disruptions as isolated; we show the ripple effect
3. **Phase Roadmap** — this is a platform, not a point solution; judges see where it goes
4. **Production Architecture** — TimescaleDB, Docker, typed APIs; built to scale, not just demo
5. **Data-Driven Recovery** — priority scoring ensures high-value PAX are recovered first

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 8, Tailwind 4, shadcn/ui, TanStack Query 5 |
| Backend | FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2.10, Python 3.13 |
| Database | TimescaleDB (PostgreSQL 16) |
| Notifications | Novu (multi-channel) |
| Containerisation | Docker Compose |

## Team

Built for the Air Arabia Hackathon.

---

*Phase 1 of Airline Resilience OS — turning disruption into competitive advantage.*
