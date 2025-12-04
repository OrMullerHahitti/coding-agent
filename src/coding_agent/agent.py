from typing import List, Dict, Any
from .clients.base import BaseLLMClient
from .tools.base import BaseTool
import json

class CodingAgent:
    def __init__(self, client: BaseLLMClient, tools: List[BaseTool], system_prompt: str = "You are a helpful coding assistant."):
        self.client = client
        self.tools = {tool.name: tool for tool in tools}
        self.history: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    def run(self, user_input: str, stream: bool = False):
        self.history.append({"role": "user", "content": user_input})
        
        while True:
            tool_schemas = self.client.format_tools(list(self.tools.values()))
            response = self.client.generate_response(self.history, tools=tool_schemas if tool_schemas else None, stream=stream)
            
            if stream:
                message_data, tool_calls = self._handle_stream(response)
                self.history.append(message_data)
                if tool_calls:
                    self._execute_tool_calls(tool_calls)
                else:
                    break
            else:
                message = response.choices[0].message
                self.history.append(message.model_dump(exclude_none=True))

                if message.tool_calls:
                    # Convert object tool_calls to dict format for consistency if needed, 
                    # but _execute_tool_calls handles list of dicts. 
                    # Let's adapt _execute_tool_calls to handle both or convert here.
                    # The message.tool_calls from non-stream are objects.
                    # Let's convert them to dicts for uniform handling.
                    tool_calls_dicts = []
                    for tc in message.tool_calls:
                        tool_calls_dicts.append({
                            "id": tc.id,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        })
                    self._execute_tool_calls(tool_calls_dicts)
                else:
                    print(f"Agent: {message.content}")
                    break

    def _handle_stream(self, response):
        content = ""
        tool_calls = []
        print("Agent: ", end="", flush=True)
        
        for chunk in response:
            delta = chunk.choices[0].delta
            if hasattr(delta, "content") and delta.content:
                print(delta.content, end="", flush=True)
                content += delta.content
            
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tc in delta.tool_calls:
                    index = tc.index if hasattr(tc, "index") else tc.get("index")
                    if len(tool_calls) <= index:
                        tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                    tool_call = tool_calls[index]
                    
                    tc_id = tc.id if hasattr(tc, "id") else tc.get("id")
                    if tc_id: tool_call["id"] += tc_id
                    
                    tc_function = tc.function if hasattr(tc, "function") else tc.get("function")
                    if tc_function:
                        name = tc_function.name if hasattr(tc_function, "name") else tc_function.get("name")
                        if name: tool_call["function"]["name"] += name
                        
                        arguments = tc_function.arguments if hasattr(tc_function, "arguments") else tc_function.get("arguments")
                        if arguments: tool_call["function"]["arguments"] += arguments
        
        print() # Newline after stream
        
        message_data = {"role": "assistant", "content": content if content else None}
        if tool_calls:
            message_data["tool_calls"] = tool_calls
            
        return message_data, tool_calls

    def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            try:
                tool_args = json.loads(tool_call["function"]["arguments"])
                if tool_name in self.tools:
                    print(f"Executing tool: {tool_name} with args: {tool_args}")
                    result = self.tools[tool_name].execute(**tool_args)
                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_name,
                        "content": str(result)
                    })
                else:
                    print(f"Tool {tool_name} not found")
            except json.JSONDecodeError:
                    print(f"Error decoding arguments for tool {tool_name}")

    def visualize(self) -> str:
        from .visualizer import AgentVisualizer
        visualizer = AgentVisualizer(list(self.tools.values()))
        return visualizer.generate_mermaid_graph()
