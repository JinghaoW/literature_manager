"""AI analysis layer — paper summarization via LLM providers.

Keep package imports lightweight so optional SDKs (anthropic/openai) are only
loaded when a concrete client is requested.
"""

from ai.base import AIClient, AnalysisResult
from ai.analyzer import analyze_paper, analyze_paper_batch, extract_paper_text
from ai.provider import create_client, load_config, save_config, config_path, default_config

__all__ = [
    "AIClient",
    "AnalysisResult",
    "ClaudeClient",
    "OpenAIClient",
    "analyze_paper",
    "analyze_paper_batch",
    "extract_paper_text",
    "create_client",
    "load_config",
    "save_config",
    "config_path",
    "default_config",
]


def __getattr__(name: str):
    if name == "ClaudeClient":
        from ai.claude_client import ClaudeClient

        return ClaudeClient
    if name == "OpenAIClient":
        from ai.openai_client import OpenAIClient

        return OpenAIClient
    raise AttributeError(f"module 'ai' has no attribute {name!r}")
