from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Inbox Assistant", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.4", alias="OPENAI_MODEL")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")

    agent_mock_mode: Literal["auto", "on", "off"] = Field(default="auto", alias="AGENT_MOCK_MODE")

    # Gmail API (draft-first)
    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str | None = Field(default=None, alias="GOOGLE_REDIRECT_URI")
    google_refresh_token: str | None = Field(default=None, alias="GOOGLE_REFRESH_TOKEN")
    google_access_token: str | None = Field(default=None, alias="GOOGLE_ACCESS_TOKEN")
    gmail_user_email: str | None = Field(default=None, alias="GMAIL_USER_EMAIL")

    # Jobs / scheduler
    job_secret: str | None = Field(default=None, alias="JOB_SECRET")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

