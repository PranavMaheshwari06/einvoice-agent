from einvoice.config import Settings


def test_defaults_use_replay_llm_and_sqlite_mlflow(monkeypatch):
    for name in ("LLM_PROVIDER", "MLFLOW_TRACKING_URI", "OPENAI_API_KEY", "OPENAI_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "replay"
    assert settings.mlflow_tracking_uri == "sqlite:///mlflow.db"
    assert settings.openai_api_key is None
    assert settings.openai_base_url is None


def test_keys_come_from_the_env_file_and_stay_hidden(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-test\nOPENAI_BASE_URL=http://llm.local/v1\n")
    settings = Settings(_env_file=env_file)
    assert settings.openai_api_key.get_secret_value() == "sk-test"
    assert "sk-test" not in repr(settings)
    assert settings.openai_base_url == "http://llm.local/v1"
