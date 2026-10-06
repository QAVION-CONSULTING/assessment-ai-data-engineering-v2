from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Union


@dataclass(frozen=True)
class LLMResponse:
    content: Union[str, Dict[str, Any]]
    model: str
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    """One call per purpose: intent, answer_check, dialog, gate_summary.

    With ``json_schema`` set, ``content`` is the parsed object; otherwise text.
    """

    async def complete(
        self,
        *,
        purpose: str,
        system: str,
        user: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse: ...
