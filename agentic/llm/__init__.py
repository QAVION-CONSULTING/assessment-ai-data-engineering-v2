from utils import settings

from .base import LLMClient, LLMResponse
from .scripted import ScriptedLLM


def build_llm() -> LLMClient:
    if settings.llm.PROVIDER == "litellm":
        from .litellm_client import LiteLLMClient

        return LiteLLMClient()
    return ScriptedLLM()


__all__ = ["LLMClient", "LLMResponse", "ScriptedLLM", "build_llm"]
