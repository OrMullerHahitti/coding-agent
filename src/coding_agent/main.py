"""Main entry point for the coding agent CLI.

Handles provider selection, tool configuration, and the main interaction loop.
"""

import argparse
import sys

import yaml

from .agent import CodingAgent
from .clients.factory import create_client, get_available_providers
from .config import get_settings
from .exceptions import (
    AgentError,
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
)
from .logging import setup_logging


def load_yaml_config() -> dict:
    """Load configuration from config.yaml if it exists."""
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def get_provider_and_model(args: argparse.Namespace, yaml_config: dict) -> tuple[str | None, str | None]:
    """Determine the provider and model to use.

    Priority order:
    1. CLI arguments
    2. Config file (config.yaml)
    3. Environment variables (via pydantic settings)
    4. Auto-detection based on available API keys
    """
    settings = get_settings()
    llm_config = yaml_config.get("llm", {})

    # priority: cli > yaml > env
    provider = args.provider or llm_config.get("provider") or settings.detect_provider()
    model = args.model or llm_config.get("model") or settings.llm_model

    return provider, model


def _start_server(host: str, port: int) -> None:
    """Start the API server."""
    try:
        import uvicorn
        from .api import app
    except ImportError:
        print("Error: API dependencies not installed.")
        print("Install with: uv sync --extra api")
        sys.exit(1)

    print(f"Starting API server at http://{host}:{port}")
    print("API docs available at http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port)


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
        choices=get_available_providers(),
        help="LLM provider to use (overrides config and auto-detection)"
    )
    parser.add_argument(
        "--model",
        help="LLM model to use (overrides config)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (also settable via CODING_AGENT_LOG_LEVEL env var)"
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the API server instead of CLI"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the API server (default: 8000)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for the API server (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--multi-agent",
        action="store_true",
        help="Run in multi-agent mode with supervisor and workers"
    )
    parser.add_argument(
        "--workers",
        nargs="+",
        choices=["coder", "researcher", "reviewer"],
        default=["coder", "researcher"],
        help="Workers to include in multi-agent mode (default: coder researcher)"
    )
    args = parser.parse_args()

    # setup logging early
    setup_logging(args.log_level)

    # handle API server mode
    if args.serve:
        _start_server(args.host, args.port)
        return

    yaml_config = load_yaml_config()
    provider, model = get_provider_and_model(args, yaml_config)

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
        llm_config = yaml_config.get("llm", {})
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

    # handle multi-agent mode
    if args.multi_agent:
        run_multi_agent(yaml_config, args.stream, args.verbose)
        return

    agent = CodingAgent(client, tools, system_prompt=system_prompt)

    if args.visualize:
        print(agent.visualize())
        return

    run_repl(agent, stream=args.stream, verbose=args.verbose)


def run_repl(agent: CodingAgent, stream: bool = False, verbose: bool = False) -> None:
    """Run the interactive REPL loop.

    Args:
        agent: The CodingAgent instance to use.
        stream: Whether to stream responses.
        verbose: Whether to print verbose output.
    """
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
            result = agent.run(user_input, stream=stream, verbose=verbose)

            # handle interrupts (ask_user tool)
            while result.is_interrupted:
                try:
                    user_response = input(f"\n[Agent asks]: {result.interrupt.question}\nYour answer: ") # type: ignore
                except (KeyboardInterrupt, EOFError):
                    print("\nInterrupt cancelled.")
                    break

                result = agent.resume(
                    result.interrupt.tool_call_id,
                    user_response,
                    stream=stream,
                    verbose=verbose,
                )

            # handle confirmation requests
            while result.is_awaiting_confirmation:
                try:
                    confirm = input(f"\n[Confirm]: {result.confirmation.message} (y/n): ").lower()
                except (KeyboardInterrupt, EOFError):
                    confirm = "n"
                result = agent.resume_confirmation(
                    result.confirmation.tool_call_id,
                    confirmed=(confirm == "y"),
                    stream=stream,
                    verbose=verbose,
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


def _create_tools_from_names(tool_names: list[str]) -> list:
    """Create tool instances from a list of tool names.

    Args:
        tool_names: List of tool name strings from config.

    Returns:
        List of tool instances.
    """
    from .tools.calculator import CalculatorTool
    from .tools.filesystem import ListDirectoryTool, ReadFileTool, WriteFileTool
    from .tools.python_repl import PythonREPLTool
    from .tools.search import TavilySearchTool
    from .tools.system import RunCommandTool

    # mapping of config names to tool classes
    tool_registry = {
        "read": ReadFileTool,
        "write": WriteFileTool,
        "list": ListDirectoryTool,
        "run_command": RunCommandTool,
        "python_repl": PythonREPLTool,
        "search_web": TavilySearchTool,
        "calculator": CalculatorTool,
    }

    tools = []
    for name in tool_names:
        if name in tool_registry:
            tools.append(tool_registry[name]())
        else:
            print(f"  Warning: Unknown tool '{name}', skipping.")

    return tools


def run_multi_agent(
    yaml_config: dict,
    stream: bool = False,
    verbose: bool = False,
) -> None:
    """Run the multi-agent system with supervisor and workers from YAML config.

    Args:
        yaml_config: Configuration loaded from config.yaml.
        stream: Whether to stream responses.
        verbose: Whether to print verbose output.
    """
    from .multi_agent import SupervisorAgent, WorkerAgent
    from .multi_agent.prompts import CODER_PROMPT, CONTEXT_PROMPT, RESEARCHER_PROMPT, REVIEWER_PROMPT

    multi_agent_config = yaml_config.get("multi_agent", {})

    if not multi_agent_config:
        print("Error: No multi_agent configuration found in config.yaml")
        print("Please add a multi_agent section with supervisor and workers config.")
        return

    # get default llm config as fallback
    default_llm = yaml_config.get("llm", {})

    # create supervisor client
    supervisor_config = multi_agent_config.get("supervisor", {})
    supervisor_provider = supervisor_config.get("provider") or default_llm.get("provider")
    supervisor_model = supervisor_config.get("model") or default_llm.get("model")

    if not supervisor_provider:
        print("Error: No provider specified for supervisor.")
        return

    print(f"Creating supervisor: {supervisor_provider}/{supervisor_model}")
    try:
        # extract client config (reasoning_effort, temperature, etc.)
        supervisor_client_config = {
            k: v for k, v in supervisor_config.items()
            if k not in ["provider", "model", "tools"]
        }
        supervisor_client = create_client(supervisor_provider, supervisor_model, supervisor_client_config)
    except ValueError as e:
        print(f"Error creating supervisor client: {e}")
        return

    # create workers from config
    workers_config = multi_agent_config.get("workers", {})

    if not workers_config:
        print("Error: No workers configured in multi_agent.workers")
        return

    # worker prompts mapping
    worker_prompts = {
        "coder": CODER_PROMPT,
        "researcher": RESEARCHER_PROMPT,
        "reviewer": REVIEWER_PROMPT,
        "context": CONTEXT_PROMPT,
    }

    # worker descriptions
    worker_descriptions = {
        "coder": "Senior software engineer for writing, reading, and modifying code.",
        "researcher": "Research specialist for finding and synthesizing information.",
        "reviewer": "Code reviewer for quality, security, and best practices analysis.",
        "context": "Codebase analyst for exploring project structure, dependencies, and architecture.",
    }

    workers = {}
    for worker_name, worker_cfg in workers_config.items():
        worker_provider = worker_cfg.get("provider") or default_llm.get("provider")
        worker_model = worker_cfg.get("model") or default_llm.get("model")

        if not worker_provider:
            print(f"  Warning: No provider for worker '{worker_name}', skipping.")
            continue

        print(f"  Creating worker '{worker_name}': {worker_provider}/{worker_model}")

        try:
            # extract client config
            worker_client_config = {
                k: v for k, v in worker_cfg.items()
                if k not in ["provider", "model", "tools"]
            }
            worker_client = create_client(worker_provider, worker_model, worker_client_config)

            # get tools for this worker
            tool_names = worker_cfg.get("tools", [])
            tools = _create_tools_from_names(tool_names)

            # get prompt (use default if worker type is known)
            prompt = worker_prompts.get(worker_name, f"You are a {worker_name} assistant.")
            description = worker_descriptions.get(worker_name, f"Worker agent: {worker_name}")

            workers[worker_name] = WorkerAgent(
                name=worker_name,
                client=worker_client,
                tools=tools,
                system_prompt=prompt,
                description=description,
            )
        except ValueError as e:
            print(f"  Error creating worker '{worker_name}': {e}")
            continue

    if not workers:
        print("Error: No workers could be created.")
        return

    # create supervisor
    supervisor = SupervisorAgent(supervisor_client, workers, verbose=verbose)
    print(f"\nMulti-Agent System Initialized with {len(workers)} workers.")
    print("Type 'exit' to quit.")
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
            result = supervisor.run(user_input, stream=stream)

            if result.content:
                print(f"\nSupervisor: {result.content}")
            elif result.error:
                print(f"\nError: {result.error}")

        except AuthenticationError as e:
            print(f"Authentication error: {e}")
        except RateLimitError as e:
            print(f"Rate limit exceeded: {e}")
        except ProviderUnavailableError as e:
            print(f"Provider unavailable: {e}")
        except AgentError as e:
            print(f"Agent error: {e}")
        except Exception as e:
            print(f"Unexpected error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
