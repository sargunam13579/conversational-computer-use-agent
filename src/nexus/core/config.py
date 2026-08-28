"""
NEXUS Configuration System.

Loads configuration from TOML files and environment variables, with a layered
override strategy: default.toml → {env}.toml → .env → environment variables.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # nexus/
_CONFIG_DIR = _PROJECT_ROOT / "config"


def _resolve_data_dir(raw: str) -> Path:
    """Expand ~ and env vars in the data directory path."""
    return Path(os.path.expandvars(os.path.expanduser(raw)))


# ---------------------------------------------------------------------------
# TOML loader
# ---------------------------------------------------------------------------


def _load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file and return its contents as a dict."""
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, returning a new dict."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


# ---------------------------------------------------------------------------
# Settings models (Pydantic v2)
# ---------------------------------------------------------------------------


class LLMOllamaSettings(BaseSettings):
    base_url: str = "http://localhost:11434"


class LLMSettings(BaseSettings):
    default_provider: str = "gemini"
    fast_model: str = "gemini-flash-lite-latest"
    smart_model: str = "gemini-flash-lite-latest"
    vision_model: str = "gemini-flash-lite-latest"
    local_model: str = "llama3"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: int = 30
    max_retries: int = 2
    ollama: LLMOllamaSettings = Field(default_factory=LLMOllamaSettings)


class VoiceWhisperSettings(BaseSettings):
    model_size: str = "base"


class VoiceSTTSettings(BaseSettings):
    language: str = "en-US"
    supported_languages: list[str] = Field(
        default_factory=lambda: ["en-US"],
    )


class VoiceTTSSettings(BaseSettings):
    voice: str = "en-US-JennyNeural"
    speed: float = 1.0
    fallback_voice: str = ""  # pyttsx3 voice ID (auto-detected if empty)


class VoiceVADSettings(BaseSettings):
    threshold: float = 0.5  # Silero confidence threshold
    min_speech_ms: int = 250  # Minimum speech duration to trigger
    energy_threshold: int = 300  # Energy pre-filter threshold


class VoiceSettings(BaseSettings):
    enabled: bool = False
    wake_word: str = "hey nexus"
    stt_provider: str = "google_web"  # google_web | vosk
    tts_provider: str = "edge"  # edge | pyttsx3
    interaction_mode: str = "voice_and_text"  # voice_and_text | voice_only | text_only
    silence_threshold_ms: int = 1500
    sample_rate: int = 16000
    interrupt_enabled: bool = True
    language: str = "en-US"
    supported_languages: list[str] = Field(
        default_factory=lambda: ["en-US", "en-IN", "ta-IN"],
    )
    whisper: VoiceWhisperSettings = Field(default_factory=VoiceWhisperSettings)
    stt: VoiceSTTSettings = Field(default_factory=VoiceSTTSettings)
    tts: VoiceTTSSettings = Field(default_factory=VoiceTTSSettings)
    vad: VoiceVADSettings = Field(default_factory=VoiceVADSettings)


class MemorySettings(BaseSettings):
    working_memory_max_turns: int = 20
    short_term_retention_hours: int = 168
    consolidation_interval_minutes: int = 60
    embedding_model: str = "all-MiniLM-L6-v2"
    max_retrieval_results: int = 10


class DatabaseSettings(BaseSettings):
    url: str = "sqlite+aiosqlite:///~/.nexus/nexus.db"
    echo: bool = False


class VectorStoreSettings(BaseSettings):
    provider: str = "chromadb"
    persist_directory: str = "~/.nexus/chromadb"
    collection_name: str = "nexus_memory"


class SecurityPermissionSettings(BaseSettings):
    low_risk: str = "auto"
    medium_risk: str = "auto"
    high_risk: str = "confirm"
    critical_risk: str = "confirm"


class SecuritySettings(BaseSettings):
    require_auth: bool = False
    session_timeout_minutes: int = 30
    max_high_risk_per_minute: int = 5
    audit_enabled: bool = True
    encryption_enabled: bool = False
    permissions: SecurityPermissionSettings = Field(default_factory=SecurityPermissionSettings)
    # Supabase Auth
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_service_role_key: str = ""


class LaptopAgentSettings(BaseSettings):
    enabled: bool = True
    allowed_directories: list[str] = Field(default_factory=lambda: ["~", "C:/Users"])
    browser: str = "chromium"
    screenshot_format: str = "png"


class AndroidAgentSettings(BaseSettings):
    enabled: bool = False
    adb_path: str = "adb"
    connection_mode: str = "usb"
    device_serial: str = ""


class CommsSettings(BaseSettings):
    enabled: bool = False
    websocket_port: int = 8765
    grpc_port: int = 50051
    heartbeat_interval_seconds: int = 10


class UISettings(BaseSettings):
    terminal_theme: str = "dark"
    show_thinking: bool = True
    show_tool_calls: bool = True


class APISettings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    api_prefix: str = "/api"


class NexusSettings(BaseSettings):
    """Root settings object for the entire NEXUS application."""

    # General
    app_name: str = "NEXUS"
    version: str = "0.1.0"
    data_dir: str = "~/.nexus"
    log_level: str = "INFO"
    log_file: str = "nexus.log"

    # Sub-configurations
    llm: LLMSettings = Field(default_factory=LLMSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    laptop_agent: LaptopAgentSettings = Field(default_factory=LaptopAgentSettings)
    android_agent: AndroidAgentSettings = Field(default_factory=AndroidAgentSettings)
    comms: CommsSettings = Field(default_factory=CommsSettings)
    ui: UISettings = Field(default_factory=UISettings)
    api: APISettings = Field(default_factory=APISettings)

    # API keys & Cloud services (loaded from env)
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    deepgram_api_key: str = ""
    elevenlabs_api_key: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_service_role_key: str = ""

    @property
    def resolved_data_dir(self) -> Path:
        """Return the data directory as a resolved Path."""
        return _resolve_data_dir(self.data_dir)

    def ensure_data_dirs(self) -> None:
        """Create the data directory tree if it doesn't exist."""
        data = self.resolved_data_dir
        data.mkdir(parents=True, exist_ok=True)
        (data / "logs").mkdir(exist_ok=True)
        (data / "chromadb").mkdir(exist_ok=True)
        (data / "screenshots").mkdir(exist_ok=True)
        (data / "recordings").mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Singleton loader
# ---------------------------------------------------------------------------

_settings: NexusSettings | None = None


def load_settings(env: str | None = None) -> NexusSettings:
    """
    Load and return the application settings.

    Resolution order (later wins):
      1. ``config/default.toml``
      2. ``config/{env}.toml``  (if env is set)
      3. ``.env`` file
      4. Real environment variables
    """
    global _settings
    if _settings is not None:
        return _settings

    # Load .env file early so env vars are available
    dotenv_path = _PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path)

    # Determine environment
    env = env or os.getenv("NEXUS_ENV", "development")

    # Load TOML layers
    base_cfg = _load_toml(_CONFIG_DIR / "default.toml")
    env_cfg = _load_toml(_CONFIG_DIR / f"{env}.toml")
    merged = _deep_merge(base_cfg, env_cfg)

    # Flatten the 'general' section to top-level (matches NexusSettings fields)
    general = merged.pop("general", {})
    merged = _deep_merge(general, merged)

    # Build settings from merged TOML + env overrides
    _settings = NexusSettings(**merged)
    _settings.ensure_data_dirs()
    return _settings


def get_settings() -> NexusSettings:
    """Return the already-loaded settings, or load with defaults."""
    global _settings
    if _settings is None:
        return load_settings()
    return _settings


def reset_settings() -> None:
    """Reset the cached settings (useful for testing)."""
    global _settings
    _settings = None
