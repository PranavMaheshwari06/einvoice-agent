from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://einvoice:einvoice@localhost:5432/einvoice"
    validator_url: str = "http://localhost:8081"
    mlflow_tracking_uri: str = "./mlruns"
    llm_provider: str = "replay"
    llm_model: str = ""
    ollama_base_url: str = "http://localhost:11434"


def get_settings() -> Settings:
    return Settings()
