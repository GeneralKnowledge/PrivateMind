from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PRIVATE_MIND_",
        env_file=".env",
        extra="ignore",
    )

    data_dir: Path = Path.home() / ".privatemind"
    db_name: str = "mind.sqlite3"
    runtime_dir_name: str = "runtime"

    # Optional OpenAI-compatible inference
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"

    max_task_retries: int = 3
    task_step_timeout_seconds: int = 120

    # Dedicated-server mode: auto-approve tool requests (lab only; default off)
    auto_approve_tool_requests: bool = False

    worker_host: str = "127.0.0.1"
    worker_port: int = 8765
    worker_use_mtls: bool = True
    worker_pki_dir_name: str = "mtls"
    worker_quarantine_failure_threshold: int = 3
    assistance_webhook_url: str | None = None

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name

    @property
    def runtime_dir(self) -> Path:
        return self.data_dir / self.runtime_dir_name

    @property
    def pki_dir(self) -> Path:
        return self.data_dir / self.worker_pki_dir_name


def get_settings() -> Settings:
    return Settings()
