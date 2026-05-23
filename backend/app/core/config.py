from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://voicepr:voicepr@localhost:5432/voicepr"
    vapi_webhook_secret: str = ""
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    chroma_dir: str = "/app/data/chroma"
    services_file: str = "/app/data/services.json"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    municipality_name: str = "Codroipo"
    appointment_open_hour: int = 9
    appointment_close_hour: int = 17
    appointment_slot_minutes: int = 30

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
