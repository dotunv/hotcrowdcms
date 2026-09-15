from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    debug: bool = True
    database_url: str = "sqlite+pysqlite:///./hotcrowd.db"
    secret_key: str = "django-insecure-dev-only"
    public_api_url: str = "http://127.0.0.1:8000"
    media_root: Path = ROOT / "media"
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "https://hotcrowd-web-player.vercel.app"
    )
    cookie_name: str = "hc_access"
    refresh_cookie_name: str = "hc_refresh"
    cookie_secure: bool | None = None
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    public_web_url: str = "http://127.0.0.1:3000"
    email_host: str = ""
    email_port: int = 587
    email_host_user: str = ""
    email_host_password: str = ""
    email_from: str = "noreply@hotcrowd.local"
    use_s3: bool = False
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_endpoint_url: str = ""
    r2_custom_domain: str = ""

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://") and "+psycopg" not in url:
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def secure_cookies(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return not self.debug

    @model_validator(mode="after")
    def reject_unsafe_production(self):
        if self.debug:
            return self
        weak = (
            not self.secret_key
            or self.secret_key.startswith("django-insecure")
            or self.secret_key in {"change-me", "test-secret-key"}
        )
        if weak:
            raise ValueError("Production requires a strong SECRET_KEY")
        if "sqlite" in self.database_url:
            raise ValueError("Production requires DATABASE_URL to point at Postgres")
        host = self.public_api_url.lower()
        if "127.0.0.1" in host or "localhost" in host:
            raise ValueError("PUBLIC_API_URL must be the public API origin so players can fetch media")
        if self.use_s3:
            missing = [
                name
                for name, value in (
                    ("R2_ACCESS_KEY_ID", self.r2_access_key_id),
                    ("R2_SECRET_ACCESS_KEY", self.r2_secret_access_key),
                    ("R2_BUCKET_NAME", self.r2_bucket_name),
                    ("R2_ENDPOINT_URL", self.r2_endpoint_url),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"USE_S3=True requires {', '.join(missing)}")
        return self


settings = Settings()
settings.media_root.mkdir(parents=True, exist_ok=True)
