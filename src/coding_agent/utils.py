import json
from typing import Any

def print_json(data: Any):
    print(json.dumps(data, indent=2))
