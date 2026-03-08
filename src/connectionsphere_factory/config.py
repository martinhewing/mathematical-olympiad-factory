"""
connectionsphere_factory/config.py
Settings — reads from environment / .env file.
All security defaults are the restrictive option.
"""
from __future__ import annotations
from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file          = ".env",
        env_file_encoding = "utf-8",
        extra             = "ignore",
    )

    # ── Auth ──────────────────────────────────────────────────────────────
    factory_api_key: str = ""

    # ── Anthropic ─────────────────────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_model:   str = "claude-sonnet-4-20250514"

    # ── Cartesia ──────────────────────────────────────────────────────────
    cartesia_api_key:  str = ""
    cartesia_voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091"
    cartesia_tutor_voice_id: str = "694f9389-aac1-45b6-b726-9d9369183238"
    cartesia_model:    str = "sonic-3"
    cartesia_stt_model: str = "ink-whisper"
    audio_storage_dir: str = "/tmp/connectionsphere_audio"

    # ── App ───────────────────────────────────────────────────────────────
    app_host:        str  = "127.0.0.1"
    app_port:        int  = 8391
    debug:           bool = False
    allowed_origins: str  = ""

    # ── Logging ───────────────────────────────────────────────────────────
    log_level:  str  = "INFO"
    json_logs:  bool = False

    # ── Rate limits ───────────────────────────────────────────────────────
    rate_limit_sessions_per_hour: int = 20
    rate_limit_submits_per_hour:  int = 100

    # ── Session behaviour ─────────────────────────────────────────────────
    probe_limit: int = 3
    max_stage_n: int = 20

    @model_validator(mode="after")
    def warn_if_keys_missing(self) -> "Settings":
        import sys
        if not self.factory_api_key:
            print(
                "\n  FACTORY_API_KEY not set — all non-public routes will return 403."
                "\n  Generate: python -c \"import secrets; print(secrets.token_hex(32))\""
                "\n  Then set it in .env\n",
                file=sys.stderr,
            )
        if not self.anthropic_api_key:
            print(
                "\n  ANTHROPIC_API_KEY not set — Claude calls will fail.\n",
                file=sys.stderr,
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
