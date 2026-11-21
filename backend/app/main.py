from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.websocket import manager
from app.database import Base, engine
from app.modules.dashboard.router import router as dashboard_router
from app.modules.disruption.router import router as disruption_router
from app.modules.notification.router import router as notification_router
from app.modules.passenger.router import router as passenger_router
from app.modules.cost.router import router as cost_router
from app.modules.recovery.router import router as recovery_router

app = FastAPI(title="Air Arabia Disruption Management", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(disruption_router)
app.include_router(passenger_router)
app.include_router(recovery_router)
app.include_router(notification_router)
app.include_router(dashboard_router)
app.include_router(cost_router)


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
