from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ModelMessage:
    role: str
    content: str


@dataclass
class ModelResponse:
    content: str
    model_id: str
    finish_reason: str = "stop"


class ModelBackend(ABC):
    """Interchangeable inference backend."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def complete(self, messages: list[ModelMessage], *, temperature: float = 0.2) -> ModelResponse:
        raise NotImplementedError
