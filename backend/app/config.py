import os
from dataclasses import dataclass


@dataclass
class ModelConfig:
    model_name: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    temperature: float = float(os.getenv("MODEL_TEMPERATURE", "0"))
    max_tokens: int = int(os.getenv("MODEL_MAX_TOKENS", "2000"))


model_config = ModelConfig()