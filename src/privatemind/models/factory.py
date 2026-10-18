from privatemind.config import Settings
from privatemind.models.base import ModelBackend
from privatemind.models.heuristic import HeuristicModel
from privatemind.models.openai_compat import OpenAICompatibleModel


def create_model(settings: Settings) -> ModelBackend:
    if settings.llm_base_url and settings.llm_api_key:
        return OpenAICompatibleModel(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    return HeuristicModel()
