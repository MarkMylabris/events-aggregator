from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_connection_string: str = (
        "postgres://postgres:postgres@localhost:5432/events_aggregator"
    )

    events_provider_url: str = "http://student-system-events-provider-web.student-system-events-provider.svc:8000"
    events_provider_api_key: str = ""

    @property
    def database_url(self) -> str:
        """Connection string in the form SQLAlchemy expects for asyncpg."""
        _, rest = self.postgres_connection_string.split("://", 1)
        return f"postgresql+asyncpg://{rest}"


settings = Settings()
