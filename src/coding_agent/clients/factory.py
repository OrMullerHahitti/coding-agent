"""Factory for creating LLM clients.

This module provides a centralized way to create LLM clients based on provider
name, using a registry pattern that makes it easy to add new providers.
"""

import os
from typing import Any

from .base import BaseLLMClient

# registry of provider configurations
_PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "anthropic": {
        "class_path": "coding_agent.clients.anthropic.AnthropicClient",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-3-5-sonnet-20240620",
    },
    "openai": {
        "class_path": "coding_agent.clients.openai.OpenAIClient",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
    },
    "together": {
        "class_path": "coding_agent.clients.together.TogetherClient",
        "api_key_env": "TOGETHER_API_KEY",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    },
    "google": {
        "class_path": "coding_agent.clients.google.GoogleClient",
        "api_key_env": "GOOGLE_API_KEY",
        "default_model": "gemini-1.5-pro-latest",
    },
}


def get_available_providers() -> list[str]:
    """Get list of available provider names.

    Returns:
        List of registered provider names.
    """
    return list(_PROVIDER_REGISTRY.keys())


def get_default_model(provider: str) -> str:
    """Get the default model for a provider.

    Args:
        provider: The provider name.

    Returns:
        The default model name.

    Raises:
        ValueError: If provider is unknown.
    """
    if provider not in _PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider}. Available: {get_available_providers()}")
    return _PROVIDER_REGISTRY[provider]["default_model"]


def create_client(
    provider: str,
    model: str | None = None,
    client_config: dict | None = None,
    api_key: str | None = None,
) -> BaseLLMClient:
    """Create an LLM client for the specified provider.

    Args:
        provider: The provider name (anthropic, openai, together, google).
        model: Optional model override. If not provided, uses provider default.
        client_config: Optional configuration dict for the client.
        api_key: Optional API key. If not provided, reads from environment.

    Returns:
        An initialized LLM client instance.

    Raises:
        ValueError: If provider is unknown or API key is not available.
    """
    if provider not in _PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider}. Available: {get_available_providers()}")

    config = _PROVIDER_REGISTRY[provider]

    # resolve API key
    resolved_key = api_key or os.getenv(config["api_key_env"])
    if not resolved_key:
        raise ValueError(f"{config['api_key_env']} not set in environment")

    # resolve model
    resolved_model = model or config["default_model"]

    # dynamically import and instantiate the client class
    client_class = _import_client_class(config["class_path"])

    return client_class(
        api_key=resolved_key,
        model=resolved_model,
        client_config=client_config,
    )


def _import_client_class(class_path: str) -> type[BaseLLMClient]:
    """Dynamically import a client class from its path.

    Args:
        class_path: Dot-separated path to the class (e.g., 'coding_agent.clients.openai.OpenAIClient').

    Returns:
        The client class.
    """
    module_path, class_name = class_path.rsplit(".", 1)

    # use lazy imports to avoid circular dependencies
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)
