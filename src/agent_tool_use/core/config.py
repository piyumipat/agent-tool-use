import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class ModelConfig:
    base_url: str
    model: str
    api_key: str
    timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "ModelConfig":
        load_dotenv(Path.cwd() / ".env", override=False)
        values = {
            "base_url": os.environ.get("LLM_BASE_URL", ""),
            "model": os.environ.get("LLM_MODEL", ""),
            "api_key": os.environ.get("LLM_API_KEY", ""),
        }
        for name, value in values.items():
            if not value.strip():
                raise ValueError(f"LLM {name} is missing from the environment")
        timeout = float(os.environ.get("LLM_TIMEOUT_SECONDS", "120"))
        if timeout <= 0:
            raise ValueError("LLM_TIMEOUT_SECONDS must be positive")
        return cls(values["base_url"], values["model"], values["api_key"], timeout)
