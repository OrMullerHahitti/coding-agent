import os
from dotenv import load_dotenv

# Import the necessary components
from coding_agent.agent import CodingAgent
from coding_agent.clients.openai import OpenAIClient
from coding_agent.clients.together import TogetherClient
from coding_agent.tools.calculator import CalculatorTool
from coding_agent.tools.search import TavilySearchTool
from coding_agent.tools.ask_user import AskUserTool
from coding_agent.prompts import SYSTEM_PROMPT

# Load environment variables (API keys)
load_dotenv()


# Example of a custom input callback for web deployment
def web_input_callback(question: str) -> str:
    """Example callback for web deployment.
    
    In a real web app, this would:
    1. Send the question to the frontend via websocket
    2. Wait for the user's response
    3. Return the response
    """
    # For this example, we'll still use input()
    print(f"\n[Web callback] Agent asks: {question}")
    return input("Your answer: ")


def main():
    # 1. Initialize the LLM Client
    # You can choose any provider you have keys for
    
    # Example: Using OpenAI
    # client = OpenAIClient(model="gpt-4o")
    
    # Example: Using Together AI
    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        print("Please set TOGETHER_API_KEY in .env")
        return
        
    client = TogetherClient(api_key=api_key, model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo")

    # 2. Define the tools you want the agent to use
    # You can pick and choose which tools to give it
    tools = [
        CalculatorTool(),
        TavilySearchTool(),
        # Use the default input() callback
        AskUserTool(),
        # OR provide a custom callback for web/api deployment:
        # AskUserTool(input_callback=web_input_callback),
    ]

    # 3. Initialize the Agent
    # Note: We pass the raw SYSTEM_PROMPT. The client will handle formatting it.
    agent = CodingAgent(client=client, tools=tools, system_prompt=SYSTEM_PROMPT)

    # 4. Run the Agent
    print("Agent initialized. Asking a question...")
    
    user_query = "Calculate 123 * 456 and then search for what year Python was released."
    
    # Option A: Non-streaming
    # response = agent.run(user_query, stream=False)
    # print(f"Response: {response}")

    # Option B: Streaming (prints to stdout as it generates)
    print("Streaming response:")
    agent.run(user_query, stream=True)

if __name__ == "__main__":
    main()

