from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "development"
    DEBUG: bool = True
    KAKAO_REST_API_KEY: str = "55e0f893de654c4ec5a2c615f7c556f9"
    KRIC_SERVICE_KEY: str = "$2a$10$0uJrclvpmuyb7H3eP6hBKOEwsapDAkxXWu14mGkRnWtY14Ubruyvm"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()