from privatemind.config import Settings
from privatemind.models.base import ModelBackend
from privatemind.models.heuristic import HeuristicModel
from privatemind.models.openai_compat import OpenAICompatibleModel
from privatemind.vault.store import AccountKind, CredentialVault


def create_model_from_vault(vault: CredentialVault | None) -> ModelBackend:
    if vault and vault.is_unlocked():
        for acct in vault.list_accounts():
            if acct.kind != AccountKind.LLM or not acct.enabled:
                continue
            base_url = acct.public.get("base_url") or acct.secrets.get("base_url")
            api_key = acct.secrets.get("api_key")
            model = acct.public.get("model") or acct.secrets.get("model") or "gpt-4o-mini"
            if base_url and api_key:
                return OpenAICompatibleModel(
                    base_url=str(base_url),
                    api_key=str(api_key),
                    model=str(model),
                )
    return HeuristicModel()


def create_model(settings: Settings, vault: CredentialVault | None = None) -> ModelBackend:
    model = create_model_from_vault(vault)
    if not isinstance(model, HeuristicModel):
        return model
    if settings.llm_base_url and settings.llm_api_key:
        return OpenAICompatibleModel(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    return model
