from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ai_provider: str = "anthropic"   # "anthropic" | "openai"
    frontend_url: str = "http://localhost:3000"

    @property
    def frontend_origins(self) -> list[str]:
        return [url.strip() for url in self.frontend_url.split(",") if url.strip()]

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        # asyncpg requires postgresql+asyncpg:// scheme
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
