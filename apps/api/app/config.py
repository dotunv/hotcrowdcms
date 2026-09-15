from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/config.py -> repo root
ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    database_url: str = "sqlite+pysqlite:///./hotcrowd.db"
    secret_key: str = "django-insecure-dev-only"
    public_api_url: str = "http://127.0.0.1:8000"
    media_root: Path = ROOT / "media"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,https://hotcrowd-web-player.vercel.app"
    cookie_name: str = "hc_access"
    cookie_secure: bool = False
    access_token_minutes: int = 60 * 24 * 7

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


settings = Settings()
settings.media_root.mkdir(parents=True, exist_ok=True)
