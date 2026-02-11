"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """VoxBridge Platform settings."""

    # App
    app_name: str = "VoxBridge"
    api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    debug: bool = False

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""  # anon key
    supabase_service_key: str = ""  # service role key
    database_url: str = ""

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 1440  # 24 hours

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_enterprise: str = ""

    # Plan limits (minutes per month)
    free_plan_minutes: int = 100
    pro_plan_minutes: int = 5000
    enterprise_plan_minutes: int = 50000

    # Rate limits
    free_max_concurrent_calls: int = 2
    pro_max_concurrent_calls: int = 20
    enterprise_max_concurrent_calls: int = 200

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
