"""Planner: classify the user's intent, then apply ordered first-match-wins rules."""

import json
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

from utils import get_logger

from .llm import LLMClient
from .messages import last_user_text
from .state import OnboardingState, PlannerDecision

logger = get_logger(__name__)

_EXCURSION_MIN_CONFIDENCE = 0.6

_INTENT_SCHEMA = {
    "type": "object",
    "required": ["kind", "confidence", "reason"],
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["answer_to_active_step", "proceed", "howto_or_meta"],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
}

_INTENT_PROMPT = (
    "Classify the user's latest message in a guided onboarding conversation. "
    "answer_to_active_step: the message answers the open question. "
    "proceed: the user wants to continue without new content. "
    "howto_or_meta: the user asks about the process, the purpose of a question or the product."
)


@dataclass(frozen=True)
class Intent:
    kind: str
    confidence: float
    source: str
    reason: str = ""


class IntentClassifier:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def classify(self, state: OnboardingState) -> Intent:
        active = state.playbook.find_step(state.playbook_state.active_step_id)
        payload = {
            "user_text": last_user_text(state.messages),
            "active_step": active.prompt if active else None,
        }
        response = await self._llm.complete(
            purpose="intent",
            system=_INTENT_PROMPT,
            user=json.dumps(payload, ensure_ascii=False),
            json_schema=_INTENT_SCHEMA,
        )
        data = response.content
        return Intent(
            kind=data["kind"],
            confidence=float(data["confidence"]),
            source="llm",
            reason=data.get("reason", ""),
        )


class PlannerRule(Protocol):
    def applies(self, state: OnboardingState, intent: Intent) -> bool: ...
    def decide(self, state: OnboardingState, intent: Intent) -> PlannerDecision: ...


def next_open_step_id(state: OnboardingState) -> Optional[str]:
    done = set(state.playbook_state.completed_step_ids)
    return next((s.id for s in state.playbook.ordered_steps() if s.id not in done), None)


def _gate_ready(state: OnboardingState) -> Optional[str]:
    pstate = state.playbook_state
    phase = state.playbook.find_phase(pstate.active_phase_id)
    gate = state.playbook.find_gate(phase.gate_id) if phase else None
    if gate is None or pstate.gate_status.get(gate.id) == "passed":
        return None
    if all(sid in pstate.completed_step_ids for sid in gate.required_step_ids):
        return gate.id
    return None


def _all_done(state: OnboardingState) -> bool:
    pstate = state.playbook_state
    return next_open_step_id(state) is None and all(
        pstate.gate_status.get(g.id) == "passed" for g in state.playbook.gates
    )


class AwaitingGateRule:
    def applies(self, state, intent):
        return state.playbook_state.awaiting_gate_id is not None

    def decide(self, state, intent):
        return PlannerDecision(
            action="review_gate",
            gate_id=state.playbook_state.awaiting_gate_id,
            reason="reply to an open gate",
        )


class ExcursionRule:
    def applies(self, state, intent):
        return intent.kind == "howto_or_meta" and intent.confidence >= _EXCURSION_MIN_CONFIDENCE

    def decide(self, state, intent):
        return PlannerDecision(
            action="handle_excursion",
            step_id=state.playbook_state.active_step_id or next_open_step_id(state),
            reason=f"intent={intent.kind} conf={intent.confidence:.2f}",
        )


class GateReadyRule:
    def applies(self, state, intent):
        return _gate_ready(state) is not None

    def decide(self, state, intent):
        return PlannerDecision(
            action="review_gate", gate_id=_gate_ready(state), reason="gate criteria met"
        )


class AllDoneRule:
    def applies(self, state, intent):
        return _all_done(state)

    def decide(self, state, intent):
        return PlannerDecision(action="finish", reason="all phases complete")


class DefaultAdvanceRule:
    def applies(self, state, intent):
        return True

    def decide(self, state, intent):
        step_id = next_open_step_id(state)
        return PlannerDecision(action="run_step", step_id=step_id, reason=f"advance to {step_id}")


DEFAULT_RULES: Sequence[PlannerRule] = (
    AwaitingGateRule(),
    ExcursionRule(),
    GateReadyRule(),
    AllDoneRule(),
    DefaultAdvanceRule(),
)


class StepPlanner:
    def __init__(self, classifier: IntentClassifier, rules: Sequence[PlannerRule] = DEFAULT_RULES):
        self._classifier = classifier
        self._rules = rules

    async def _intent(self, state: OnboardingState) -> Intent:
        if state.step_data.user_message_consumed or not last_user_text(state.messages):
            return Intent(kind="proceed", confidence=1.0, source="structural")
        if state.playbook_state.awaiting_gate_id is not None:
            return Intent(kind="answer_to_active_step", confidence=1.0, source="structural")
        return await self._classifier.classify(state)

    async def decide(self, state: OnboardingState) -> PlannerDecision:
        intent = await self._intent(state)
        for rule in self._rules:
            if rule.applies(state, intent):
                decision = rule.decide(state, intent).model_copy(update={"intent_kind": intent.kind})
                logger.info(
                    "planner conv=%s rule=%s action=%s step=%s",
                    state.conversation_id, type(rule).__name__, decision.action, decision.step_id,
                )
                return decision
        raise RuntimeError("no planner rule matched; DefaultAdvanceRule must be last")
