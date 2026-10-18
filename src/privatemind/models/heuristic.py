"""Deterministic model for demos and tests — no external API required."""

import json
import re

from privatemind.models.base import ModelBackend, ModelMessage, ModelResponse


class HeuristicModel(ModelBackend):
    """
    Parses a simple JSON action block from the task description or emits
    a default plan for built-in demo tasks.
    """

    def __init__(self, model_id: str = "heuristic-local") -> None:
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def complete(self, messages: list[ModelMessage], *, temperature: float = 0.2) -> ModelResponse:
        user_text = "\n".join(m.content for m in messages if m.role == "user")
        action_match = re.search(r'"action"\s*:\s*"(\w+)"', user_text)
        if action_match:
            return ModelResponse(content=user_text, model_id=self._model_id)

        memory_keys = self._memory_keys_from_context(user_text)

        if "Milestone 1: persistence demo" in user_text:
            if "demo.sha256" in memory_keys and "demo.result" not in memory_keys:
                payload = {
                    "action": "use_tool",
                    "tool": "remember",
                    "arguments": {
                        "key": "demo.result",
                        "content": "Milestone 1 persistence demo completed.",
                        "kind": "fact",
                    },
                    "reasoning": "Hash stored; persist completion note.",
                }
                return ModelResponse(content=json.dumps(payload), model_id=self._model_id)
            payload = {
                "action": "use_tool",
                "tool": "compute_sha256",
                "arguments": {"text": "privatemind-milestone-1"},
                "reasoning": "Task asks for a deterministic hash; use local tool.",
            }
            return ModelResponse(content=json.dumps(payload), model_id=self._model_id)

        payload = {
            "action": "complete_task",
            "summary": "No further steps inferred; marking complete.",
        }
        return ModelResponse(content=json.dumps(payload), model_id=self._model_id)

    @staticmethod
    def _memory_keys_from_context(user_text: str) -> set[str]:
        block = re.search(
            r"Relevant memory \(retrieve only; may be unverified\):\n(\[.*?\])\nChoose the next action\.",
            user_text,
            re.DOTALL,
        )
        if not block:
            return set()
        try:
            items = json.loads(block.group(1))
        except json.JSONDecodeError:
            return set()
        return {str(item.get("key")) for item in items if item.get("key")}
