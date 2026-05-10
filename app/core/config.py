from pydantic_settings import BaseSettings
from pydantic import field_validator, AnyHttpUrl
from typing import Optional, List
import secrets


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Literary Haven"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Security
    SECRET_KEY: str
    REFRESH_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    CSRF_SECRET_KEY: str = secrets.token_hex(32)

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    AUTH_RATE_LIMIT_PER_MINUTE: int = 5

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Uploads
    MAX_UPLOAD_SIZE_MB: int = 5
    UPLOAD_DIR: str = "uploads"

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@literaryhaven.ru"
    EMAILS_FROM_NAME: str = "Literary Haven"

    # OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_BASE: str = "http://localhost:8000"

    # VK OAuth
    VK_CLIENT_ID: str = ""
    VK_CLIENT_SECRET: str = ""

    @property
    def GOOGLE_REDIRECT_URI(self) -> str:
        return f"{self.OAUTH_REDIRECT_BASE}/api/v1/auth/google/callback"

    @property
    def GITHUB_REDIRECT_URI(self) -> str:
        return f"{self.OAUTH_REDIRECT_BASE}/api/v1/auth/github/callback"

    @property
    def VK_REDIRECT_URI(self) -> str:
        return f"{self.OAUTH_REDIRECT_BASE}/api/v1/auth/vk/callback"

    # Admin seed
    FIRST_ADMIN_EMAIL: str = "admin@literaryhaven.ru"
    FIRST_ADMIN_PASSWORD: str = "Admin1234!"
    FIRST_ADMIN_USERNAME: str = "admin"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
