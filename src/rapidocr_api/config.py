import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def load_api_keys(path: Path) -> list[str]:
    if not path.exists():
        return []

    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid API keys TOML file: {path}") from exc

    raw_keys = data.get("api_keys")
    if raw_keys is None and isinstance(data.get("auth"), dict):
        raw_keys = data["auth"].get("api_keys")

    if raw_keys is None:
        return []
    if not isinstance(raw_keys, list) or not all(isinstance(key, str) for key in raw_keys):
        raise ValueError("API keys TOML must define api_keys as a list of strings")

    return [key.strip() for key in raw_keys if key.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "rapidocr-fastapi"
    app_version: str = "0.1.0"
    api_keys_file: Path = Field(default=Path("api-keys.toml"), alias="API_KEYS_FILE")
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")
    ocr_concurrency: int = Field(default=1, alias="OCR_CONCURRENCY")
    rapidocr_use_cls: bool = Field(default=False, alias="RAPIDOCR_USE_CLS")

    enable_metrics: bool = Field(default=True, alias="ENABLE_METRICS")
    metrics_require_api_key: bool = Field(default=False, alias="METRICS_REQUIRE_API_KEY")

    webui_dir: Path | None = Field(default=None, alias="WEBUI_DIR")

    @property
    def api_keys(self) -> list[str]:
        return load_api_keys(self.api_keys_file)

    @field_validator("max_upload_bytes", "ocr_concurrency")
    @classmethod
    def positive_int(cls, value):
        if value <= 0:
            raise ValueError("must be positive")
        return value


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise ValueError("Invalid application settings") from exc
