"""Main entry point for the coding agent CLI.

Handles provider selection, tool configuration, and the main interaction loop.
"""

import os
import sys

from dotenv import load_dotenv

# load environment variables
load_dotenv()

import argparse

import yaml

from .agent import CodingAgent
from .exceptions import (
    AgentError,
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
)


def load_config() -> dict:
    """Load configuration from config.yaml if it exists."""
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def get_provider_and_model(args: argparse.Namespace, config: dict) -> tuple[str | None, str | None]:
    """Determine the provider and model to use.

    Priority order:
    1. CLI arguments
    2. Config file
    3. Environment variable
    4. Auto-detection based on available API keys
    """
    llm_config = config.get("llm", {})

    provider = args.provider or llm_config.get("provider") or os.getenv("LLM_PROVIDER")
    model = args.model or llm_config.get("model")

    # auto-detect provider based on available API keys
    if not provider:
        if os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        elif os.getenv("TOGETHER_API_KEY"):
            provider = "together"
        elif os.getenv("GOOGLE_API_KEY"):
            provider = "google"

    return provider, model


def create_client(provider: str, model: str | None, client_config: dict | None = None):
    """Create the appropriate LLM client.

    Args:
        provider: The provider name (anthropic, openai, together, google)
        model: Optional model override
        client_config: Optional configuration for the client

    Returns:
        An initialized LLM client

    Raises:
        ValueError: If API key is not set or provider is unknown
    """
    if provider == "anthropic":
        from .clients.anthropic import AnthropicClient
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")
        return AnthropicClient(
            api_key=api_key,
            model=model or "claude-3-5-sonnet-20240620",
            client_config=client_config
        )

    elif provider == "openai":
        from .clients.openai import OpenAIClient
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        return OpenAIClient(
            api_key=api_key,
            model=model or "gpt-4o",
            client_config=client_config
        )

    elif provider == "together":
        from .clients.together import TogetherClient
        api_key = os.getenv("TOGETHER_API_KEY")
        if not api_key:
            raise ValueError("TOGETHER_API_KEY not set in environment")
        return TogetherClient(
            api_key=api_key,
            model=model or "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            client_config=client_config
        )

    elif provider == "google":
        from .clients.google import GoogleClient
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in environment")
        return GoogleClient(
            api_key=api_key,
            model=model or "gemini-1.5-pro-latest",
            client_config=client_config
        )

    else:
        raise ValueError(f"Unknown provider: {provider}")


def main():
    """Main entry point for the coding agent CLI."""
    parser = argparse.ArgumentParser(description="Coding Agent CLI")
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Generate a Mermaid graph of the agent structure"
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming responses"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--provider",
        choices=["together", "openai", "anthropic", "google"],
        help="LLM provider to use (overrides config and auto-detection)"
    )
    parser.add_argument(
        "--model",
        help="LLM model to use (overrides config)"
    )
    args = parser.parse_args()

    config = load_config()
    provider, model = get_provider_and_model(args, config)

    if not provider:
        print("Error: No LLM provider specified and no API keys found.")
        print("Please set one of the following:")
        print("  - LLM_PROVIDER environment variable")
        print("  - provider in config.yaml")
        print("  - ANTHROPIC_API_KEY, OPENAI_API_KEY, TOGETHER_API_KEY, or GOOGLE_API_KEY")
        sys.exit(1)

    print(f"Using provider: {provider}")
    if model:
        print(f"Using model: {model}")

    try:
        # extract client config parameters (excluding provider/model which are handled separately)
        llm_config = config.get("llm", {})
        client_config = {
            k: v for k, v in llm_config.items()
            if k not in ["provider", "model"]
        }

        client = create_client(provider, model, client_config)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # initialize tools
    from .prompts import SYSTEM_PROMPT, THOUGHT_SUFFIX
    from .tools.ask_user import AskUserTool
    from .tools.calculator import CalculatorTool
    from .tools.filesystem import ListDirectoryTool, ReadFileTool, WriteFileTool
    from .tools.python_repl import PythonREPLTool
    from .tools.search import TavilySearchTool
    from .tools.system import RunCommandTool

    tools = [
        CalculatorTool(),
        ListDirectoryTool(),
        ReadFileTool(),
        WriteFileTool(),
        RunCommandTool(),
        PythonREPLTool(),
        TavilySearchTool(),
        AskUserTool(use_interrupt=True),  # use interrupt mode
    ]

    system_prompt = SYSTEM_PROMPT
    if args.verbose:
        system_prompt += THOUGHT_SUFFIX

    agent = CodingAgent(client, tools, system_prompt=system_prompt)

    if args.visualize:
        print(agent.visualize())
        return

    print("Coding Agent Initialized. Type 'exit' to quit.")
    print("-" * 50)

    while True:
        try:
            user_input = input("You: ")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        if not user_input.strip():
            continue

        try:
            result = agent.run(user_input, stream=args.stream, verbose=args.verbose)

            # handle interrupts (ask_user tool)
            while result.is_interrupted:
                try:
                    user_response = input(f"\n[Agent asks]: {result.interrupt.question}\nYour answer: ")
                except (KeyboardInterrupt, EOFError):
                    print("\nInterrupt cancelled.")
                    break

                result = agent.resume(
                    result.interrupt.tool_call_id,
                    user_response,
                    stream=args.stream,
                    verbose=args.verbose,
                )

        except AuthenticationError as e:
            print(f"Authentication error: {e}")
            print("Please check your API key.")
        except RateLimitError as e:
            print(f"Rate limit exceeded: {e}")
            print("Please wait a moment and try again.")
        except ProviderUnavailableError as e:
            print(f"Provider unavailable: {e}")
            print("Please try again later.")
        except AgentError as e:
            print(f"Agent error: {e}")
        except Exception as e:
            print(f"Unexpected error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
