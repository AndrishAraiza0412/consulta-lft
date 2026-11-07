import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "postgresql://lft:lft@127.0.0.1:15433/lft")
    )
    llm_base_url: str = field(
        default_factory=lambda: _env("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    )
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY", "ollama"))
    chat_model: str = field(default_factory=lambda: _env("CHAT_MODEL", "qwen2.5:3b-instruct"))
    embed_model: str = field(default_factory=lambda: _env("EMBED_MODEL", "bge-m3"))
    source_version: str = field(default_factory=lambda: _env("SOURCE_VERSION", "DOF-2026-05-14"))
    top_k: int = field(default_factory=lambda: int(_env("TOP_K", "5")))
    min_similarity: float = field(default_factory=lambda: float(_env("MIN_SIMILARITY", "0.5")))
    max_output_tokens: int = field(default_factory=lambda: int(_env("MAX_OUTPUT_TOKENS", "500")))
    max_context_chars: int = field(default_factory=lambda: int(_env("MAX_CONTEXT_CHARS", "6000")))
    monthly_limit_usd: float = field(default_factory=lambda: float(_env("MONTHLY_LIMIT_USD", "5")))
    price_input_per_mtok: float = field(
        default_factory=lambda: float(_env("PRICE_INPUT_PER_MTOK", "0"))
    )
    price_output_per_mtok: float = field(
        default_factory=lambda: float(_env("PRICE_OUTPUT_PER_MTOK", "0"))
    )


def get_settings() -> Settings:
    return Settings()
