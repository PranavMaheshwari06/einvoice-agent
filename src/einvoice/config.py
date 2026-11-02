from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://einvoice:einvoice@localhost:5432/einvoice"
    validator_url: str = "http://localhost:8081"
    mlflow_tracking_uri: str = "sqlite:///mlflow.db"
    llm_provider: str = "replay"
    llm_model: str = ""
    ollama_base_url: str = "http://localhost:11434"
    # Read here and passed to the chat clients, because .env is not copied into os.environ.
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    anthropic_api_key: SecretStr | None = None


def get_settings() -> Settings:
    return Settings()
