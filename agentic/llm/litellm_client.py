"""Real-provider client via litellm (install with ``uv sync --extra llm``).

Model ids per purpose come from ``[default.llm.models]`` in utils/settings.toml,
for example ``openai/gpt-5-mini``, ``anthropic/claude-sonnet-4-5``,
``bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0``, ``azure/<deployment>``
or ``ollama/llama3.1``.
"""

import json
from typing import Any, Dict, Optional

from utils import settings

from .base import LLMResponse


class LiteLLMClient:
    def __init__(self) -> None:
        import litellm

        self._litellm = litellm
        self._models = {k.lower(): v for k, v in settings.llm.models.items()}

    async def complete(
        self,
        *,
        purpose: str,
        system: str,
        user: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        model = self._models[purpose]
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": float(settings.llm.TEMPERATURE),
        }
        if json_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": purpose, "schema": json_schema},
            }
        response = await self._litellm.acompletion(**kwargs)
        text = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResponse(
            content=json.loads(text) if json_schema is not None else text,
            model=model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )
