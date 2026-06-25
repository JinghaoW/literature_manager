"""Provider factory — reads config file and returns the right AI client."""

from __future__ import annotations

import json
from pathlib import Path

from ai.base import AIClient

def _get_config_path() -> Path:
    """Config file next to the exe (PyInstaller) or in project root."""
    import sys
    if getattr(sys, "frozen", False):
        # Running as PyInstaller exe — config next to exe.
        return Path(sys.executable).parent / ".paper_notes_config.json"
    return Path(__file__).resolve().parent.parent / ".paper_notes_config.json"

_CONFIG_PATH = _get_config_path()

# Provider defaults.
_PRESETS: dict[str, dict] = {
    "claude": {
        "provider": "claude",
        "model": "claude-haiku-4-5-20251001",
    },
    "openai": {
        "provider": "openai",
        "model": "gpt-4o-mini",
    },
    "deepseek": {
        "provider": "openai",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
    },
    "ollama": {
        "provider": "openai",
        "model": "llama3",
        "base_url": "http://localhost:11434/v1",
    },
}


def load_config() -> dict | None:
    """Load the config file, or return None if not found."""
    if not _CONFIG_PATH.is_file():
        return None
    try:
        return json.loads(_CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_config(data: dict) -> None:
    """Write the config file."""
    _CONFIG_PATH.write_text(json.dumps(data, indent=2))


def create_client(config: dict) -> AIClient:
    """Create an AI client from a config dict.

    Config keys:
        provider: "claude" or "openai"
        api_key:  the API key
        model:    model name (optional, uses preset default)
        base_url: custom API base URL (optional)

    For provider="claude" → ClaudeClient (Anthropic).
    For provider="openai" → OpenAIClient (works for OpenAI, DeepSeek, Ollama, etc.)
    """
    provider = config.get("provider", "openai")
    api_key = config.get("api_key", "")
    if not api_key:
        raise ValueError("No api_key in config")

    model = config.get("model") or _PRESETS.get(provider, {}).get("model", "gpt-4o-mini")
    base_url = config.get("base_url")

    if provider == "claude":
        from ai.claude_client import ClaudeClient
        return ClaudeClient(api_key=api_key, model=model)

    # OpenAI-compatible (openai, deepseek, ollama, custom).
    from ai.openai_client import OpenAIClient
    preset = _PRESETS.get(provider, {})
    if not base_url:
        base_url = preset.get("base_url")
    if not model:
        model = preset.get("model", "gpt-4o-mini")

    return OpenAIClient(api_key=api_key, model=model, base_url=base_url)


def config_path() -> Path:
    """Return the config file path for display."""
    return _CONFIG_PATH


def default_config(provider: str = "claude") -> dict:
    """Generate a template config for the given provider."""
    preset = _PRESETS.get(provider, _PRESETS["claude"])
    return {
        "provider": preset["provider"],
        "api_key": "YOUR_API_KEY_HERE",
        "model": preset["model"],
        "base_url": preset.get("base_url", ""),
    }
