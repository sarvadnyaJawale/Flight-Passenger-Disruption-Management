from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://disruption:disruption@localhost:5432/disruption"
    RECOVERY_JWT_SECRET: str = "hackathon-secret-change-me"
    RECOVERY_JWT_EXPIRE_HOURS: int = 24
    FRONTEND_URL: str = "http://localhost:5173"
    NOVU_API_KEY: str = ""
    DATA_DIR: str = "../data"

    model_config = {"env_file": ".env"}


settings = Settings()
