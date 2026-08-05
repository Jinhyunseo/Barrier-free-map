from typing import List, Union
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "GCP Backend API"
    VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./test.db",  # 개발용 기본 SQLite, 실제 동작 시 .env의 MySQL URL로 오버라이드
        description="SQLAlchemy DB Connection URL",
    )

    # External APIs
    KAKAO_API_KEY: str = Field(default="", description="Kakao REST API Key")
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key")

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
