import sys
import io
from typing import Dict, Any
from .base import BaseTool

class PythonREPLTool(BaseTool):
    def __init__(self):
        self.globals = {}
        self.locals = {}

    @property
    def name(self) -> str:
        return "python_repl"

    @property
    def description(self) -> str:
        return "Execute Python code dynamically. Use this to run calculations, data processing, or test snippets. The code runs in a persistent environment."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute."
                }
            },
            "required": ["code"]
        }

    def execute(self, code: str) -> str:
        old_stdout = sys.stdout
        redirected_output = io.StringIO()
        sys.stdout = redirected_output

        try:
            exec(code, self.globals, self.locals)
            return redirected_output.getvalue()
        except Exception as e:
            return f"Error executing Python code: {str(e)}"
        finally:
            sys.stdout = old_stdout
