"""Dialog executor: open a step, judge the user's answer, or answer a side question."""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from utils import get_logger, settings

from .llm import LLMClient
from .messages import last_user_text, recent_turns
from .playbook import Step
from .state import DialogResult, OnboardingState, PlannerDecision
from .tools import CompanyResearchTool

logger = get_logger(__name__)

_THRESHOLD = float(settings.agentic.FREE_TEXT_CONFIDENCE_THRESHOLD)

_ANSWER_CHECK_SCHEMA = {
    "type": "object",
    "required": ["answered", "confidence", "summary"],
    "properties": {
        "answered": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
        "missing": {"type": "array", "items": {"type": "string"}},
    },
}

_ANSWER_CHECK_PROMPT = (
    "You check whether the active step of a guided German onboarding conversation is "
    "complete after the user's latest message. A question, a remark or an answer to a "
    "different question does not complete the step. summary: the collected answer in one "
    "German sentence. missing: what is still open. confidence: probability that your "
    "verdict is correct."
)

_DIALOG_PROMPT = (
    "Du bist ein Onboarding-Assistent einer Data-&-AI-Beratung. Antworte knapp und "
    "freundlich auf Deutsch. Stelle immer genau eine Frage."
)


@dataclass(frozen=True)
class AnswerVerdict:
    answered: bool
    confidence: float = 0.0
    summary: str = ""
    missing: List[str] = field(default_factory=list)


class AnswerChecker:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def check(self, *, step: Step, messages, user_text: str) -> AnswerVerdict:
        payload = {
            "step": step.model_dump(include={"prompt", "objective", "options", "success_criteria"}),
            "dialog": recent_turns(messages),
            "user_message": user_text,
        }
        try:
            response = await self._llm.complete(
                purpose="answer_check",
                system=_ANSWER_CHECK_PROMPT,
                user=json.dumps(payload, ensure_ascii=False),
                json_schema=_ANSWER_CHECK_SCHEMA,
            )
        except Exception as exc:
            # Never block the user because the judge model is unavailable.
            logger.warning("answer check failed, accepting answer: %s", exc)
            return AnswerVerdict(answered=True, confidence=0.5, summary=user_text)
        data = response.content
        return AnswerVerdict(
            answered=bool(data.get("answered")),
            confidence=float(data.get("confidence", 0.0)),
            summary=data.get("summary") or user_text,
            missing=[str(m) for m in data.get("missing") or []],
        )


class DialogExecutor:
    def __init__(
        self,
        llm: LLMClient,
        answer_checker: AnswerChecker,
        research: CompanyResearchTool,
    ) -> None:
        self._llm = llm
        self._checker = answer_checker
        self._research = research

    async def _say(self, state: OnboardingState, mode: str, step: Step, **extra: Any) -> str:
        research_notes: Optional[Dict[str, Any]] = extra.get("research")
        system = _DIALOG_PROMPT
        if research_notes:
            system += (
                "\n\nVerifizierte Registerdaten (vertrauenswürdig, bitte befolgen):\n"
                + json.dumps(research_notes, ensure_ascii=False)
            )
        payload = {
            "mode": mode,
            "step": step.model_dump(include={"prompt", "objective", "options"}),
            "dialog": recent_turns(state.messages),
            **extra,
        }
        response = await self._llm.complete(
            purpose="dialog", system=system, user=json.dumps(payload, ensure_ascii=False)
        )
        return str(response.content)

    def _research_for(self, state: OnboardingState) -> Optional[Dict[str, Any]]:
        answer = state.playbook_state.answers.get("s1_company_name") or {}
        return self._research.lookup(str(answer.get("summary") or ""))

    async def execute(self, state: OnboardingState) -> Dict[str, Any]:
        decision: PlannerDecision = state.step_data.planner_decision
        step = state.playbook.find_step(decision.step_id)
        pstate = state.playbook_state.model_copy(deep=True)
        turn = state.step_data.model_copy(deep=True)
        user_text = "" if turn.user_message_consumed else last_user_text(state.messages)

        if decision.action == "handle_excursion":
            text = await self._say(state, "excursion", step, question=user_text)
            turn.user_message_consumed = True
            turn.turn_texts.append(text)
            turn.last_dialog_result = DialogResult(step_id=step.id, step_accepted=False)
            return {"playbook_state": pstate, "step_data": turn, "chat_state": "waiting_for_user"}

        if step.id not in pstate.shown_step_ids or not user_text:
            research = self._research_for(state) if step.uses_research else None
            text = await self._say(state, "open_step", step, research=research)
            if step.id not in pstate.shown_step_ids:
                pstate.shown_step_ids.append(step.id)
            pstate.active_step_id = step.id
            pstate.active_phase_id = state.playbook.phase_of(step.id).id
            turn.turn_texts.append(text)
            turn.last_dialog_result = DialogResult(step_id=step.id, step_accepted=False)
            return {"playbook_state": pstate, "step_data": turn, "chat_state": "waiting_for_user"}

        verdict = await self._checker.check(step=step, messages=state.messages, user_text=user_text)
        if verdict.answered:
            turn.user_message_consumed = True
            pstate.completed_step_ids.append(step.id)
            pstate.answers[step.id] = {
                "summary": verdict.summary,
                "raw": user_text,
                "confidence": verdict.confidence,
            }
            text = await self._say(state, "acknowledge", step)
            turn.turn_texts.append(text)
            turn.last_dialog_result = DialogResult(
                step_id=step.id, step_accepted=True, extraction_confidence=verdict.confidence
            )
            return {"playbook_state": pstate, "step_data": turn, "chat_state": "in_progress"}

        # The clarification is part of the same exchange, not a new question.
        text = await self._say(state, "ask_missing", step, missing=verdict.missing)
        turn.turn_texts.append(text)
        turn.last_dialog_result = DialogResult(
            step_id=step.id, step_accepted=False, extraction_confidence=verdict.confidence
        )
        return {"playbook_state": pstate, "step_data": turn, "chat_state": "clarifying"}
