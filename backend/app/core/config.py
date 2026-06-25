from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""
    allowed_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002"

    # Absolute paths resolved at startup
    data_dir: Path = Path(__file__).parents[3] / "data"
    datasets_dir: Path | None = None
    outputs_dir: Path = Path(__file__).parents[3] / "outputs"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)

# Support both layouts:
# 1) data/<source>/charts.json (legacy)
# 2) data/datasets/<source>/charts.json (current)
if settings.datasets_dir is None:
    candidate = settings.data_dir / "datasets"
    settings.datasets_dir = candidate if candidate.exists() else settings.data_dir

# Support outputs in either root /outputs (legacy) or data/outputs (current)
if not settings.outputs_dir.exists():
    migrated_outputs = settings.data_dir / "outputs"
    if migrated_outputs.exists():
        settings.outputs_dir = migrated_outputs

settings.datasets_dir.mkdir(parents=True, exist_ok=True)
settings.outputs_dir.mkdir(parents=True, exist_ok=True)
(settings.outputs_dir / "runs").mkdir(exist_ok=True)
