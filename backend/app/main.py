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
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    from app.data_loader.loader import load_all
    load_all(settings.DATA_DIR)


@app.get("/api/health")
def health():
    return {"status": "ok"}
