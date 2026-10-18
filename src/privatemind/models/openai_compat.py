"""OpenAI-compatible HTTP chat completions backend."""

import httpx

from privatemind.models.base import ModelBackend, ModelMessage, ModelResponse


class OpenAICompatibleModel(ModelBackend):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    @property
    def model_id(self) -> str:
        return self._model

    def complete(self, messages: list[ModelMessage], *, temperature: float = 0.2) -> ModelResponse:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(f"{self._base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        choice = data["choices"][0]
        return ModelResponse(
            content=choice["message"]["content"],
            model_id=self._model,
            finish_reason=choice.get("finish_reason", "stop"),
        )
