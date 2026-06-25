"""AI analysis layer — paper summarization via LLM providers."""

from ai.base import AIClient, AnalysisResult
from ai.claude_client import ClaudeClient
from ai.openai_client import OpenAIClient
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
