from pathlib import Path
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
import secrets

ROOT = Path(os.environ.get("BIOLOGY_ROOT", Path.cwd())).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./biology.db"
    jwt_secret: str = secrets.token_urlsafe(48)
    cors_origins: list[str] = ["http://localhost:3000"]
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""


settings = Settings()
