"""LangGraph state for the onboarding step orchestrator."""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from langgraph_base.state import BaseAgentState

from .playbook import Playbook, PlaybookState


class PlannerDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["run_step", "handle_excursion", "review_gate", "finish"]
    step_id: Optional[str] = None
    gate_id: Optional[str] = None
    intent_kind: Optional[str] = None
    reason: str = ""


class DialogResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: Optional[str]
    step_accepted: bool
    extraction_confidence: Optional[float] = None


class TurnData(BaseModel):
    """Rebuilt for every turn; never persisted."""

    model_config = ConfigDict(extra="forbid")

    planner_decision: Optional[PlannerDecision] = None
    last_dialog_result: Optional[DialogResult] = None
    turn_texts: List[str] = Field(default_factory=list)
    # True once a step or gate has used the user's message this turn.
    user_message_consumed: bool = False


class OnboardingState(BaseAgentState[TurnData]):
    playbook: Playbook
    playbook_state: PlaybookState
