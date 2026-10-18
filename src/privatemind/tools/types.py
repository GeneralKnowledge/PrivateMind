from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    ok: bool
    output: Any
    detail: str = ""
