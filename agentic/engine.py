"""Turn engine: load conversation, run one graph turn, persist the result."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from utils import get_logger, settings

from .graph_factory import build_graph
from .llm import LLMClient, build_llm
from .playbook import Playbook, PlaybookState, load_playbook
from .state import OnboardingState, TurnData
from .tools import CompanyResearchTool
from .usage import TrackedLLM, UsageTracker

logger = get_logger(__name__)


@dataclass
class Conversation:
    conversation_id: str
    user_id: str
    playbook_state: PlaybookState
    messages: List[Dict[str, Any]] = field(default_factory=list)


_CONVERSATIONS: Dict[str, Conversation] = {}


class OnboardingEngine:
    def __init__(
        self,
        *,
        llm: Optional[LLMClient] = None,
        research: Optional[CompanyResearchTool] = None,
        playbook: Optional[Playbook] = None,
    ) -> None:
        self.usage = UsageTracker()
        self.playbook = playbook or load_playbook(settings.agentic.PLAYBOOK)
        self._llm = TrackedLLM(llm or build_llm(), self.usage)
        self._graph = build_graph(llm=self._llm, research=research or CompanyResearchTool())

    def conversation(self, conversation_id: str) -> Conversation:
        return _CONVERSATIONS[conversation_id]

    async def start(self, conversation_id: str, user_id: str) -> List[str]:
        _CONVERSATIONS[conversation_id] = Conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            playbook_state=PlaybookState.start(self.playbook),
        )
        return await self._run(conversation_id, user_text=None)

    async def turn(self, conversation_id: str, user_text: str) -> List[str]:
        return await self._run(conversation_id, user_text=user_text)

    async def _run(self, conversation_id: str, user_text: Optional[str]) -> List[str]:
        conv = _CONVERSATIONS[conversation_id]
        if user_text is not None:
            conv.messages.append({"role": "user", "content": user_text})
        state = OnboardingState(
            conversation_id=conv.conversation_id,
            user_id=conv.user_id,
            messages=list(conv.messages),
            step_data=TurnData(),
            playbook=self.playbook,
            playbook_state=conv.playbook_state,
        )
        with self.usage.span("turn"):
            result = await self._graph.workflow.ainvoke(
                state, config={"recursion_limit": int(settings.agentic.RECURSION_LIMIT)}
            )
        turn: TurnData = result["step_data"]
        conv.playbook_state = result["playbook_state"]
        for text in turn.turn_texts:
            conv.messages.append({"role": "assistant", "content": text})
        return list(turn.turn_texts)
