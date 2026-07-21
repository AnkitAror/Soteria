"""Application settings loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql://soteria:soteria@localhost:5432/soteria"
    redis_url: str = "redis://localhost:6379/0"

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"
    plaid_webhook_verification_enabled: bool = False
    # Public URL Plaid should POST webhooks to, e.g. an ngrok tunnel ending in
    # /plaid/webhook. Left blank, Link tokens are created with no webhook
    # destination at all (Plaid has nowhere to send events).
    plaid_webhook_url: str = ""

    encryption_key: str = ""

    insights_generation_interval_minutes: int = 360

    supabase_url: str = ""
    supabase_anon_key: str = ""

    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-flash-latest"
    gemini_embedding_model: str = "gemini-embedding-001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
