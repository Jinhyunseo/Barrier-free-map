from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Seongnam Barrier-Free Navigation"
    VERSION: str = "2.0.0"
    DEBUG: bool = True

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "seongnam_nav_db"

    KAKAO_REST_API_KEY: str = ""

    # 2차 프로토타입 현장 사진 검증(F-09)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash"
    AI_CONFIDENCE_THRESHOLD: float = 65.0
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024

    # 개발 테스트용
    AI_TEST_FORCE_APPROVE: bool = False

    # 기존 코드와의 호환성 때문에 남겨 둡니다.
    OPENAI_API_KEY: str = ""

    SECRET_KEY: str = "CHANGE_ME"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    ELEVATOR_API_KEY: str = ""
    BUS_API_KEY: str = ""
    SUBWAY_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def async_database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


settings = Settings()
