"""Gate reviewer: summarise a finished phase and let the user confirm or reopen it."""

import json
import re
from typing import Any, Dict

from .llm import LLMClient
from .messages import last_user_text
from .state import OnboardingState

_YES = re.compile(r"\b(ja|jep|passt|korrekt|richtig|ok|okay|yes)\b", re.IGNORECASE)
_NO = re.compile(r"\b(nein|no|falsch|korrigieren|ändern)\b", re.IGNORECASE)

_SUMMARY_PROMPT = "Fasse die Antworten der Phase in zwei bis drei deutschen Sätzen zusammen."


class GateReviewer:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def execute(self, state: OnboardingState) -> Dict[str, Any]:
        decision = state.step_data.planner_decision
        gate = state.playbook.find_gate(decision.gate_id)
        pstate = state.playbook_state.model_copy(deep=True)
        turn = state.step_data.model_copy(deep=True)

        if pstate.awaiting_gate_id != gate.id:
            answers = [
                {"title": state.playbook.find_step(sid).title, "summary": pstate.answers[sid]["summary"]}
                for sid in gate.required_step_ids
            ]
            response = await self._llm.complete(
                purpose="gate_summary",
                system=_SUMMARY_PROMPT,
                user=json.dumps({"gate": gate.title, "answers": answers}, ensure_ascii=False),
            )
            pstate.awaiting_gate_id = gate.id
            pstate.gate_status[gate.id] = "pending"
            turn.turn_texts.append(f"{response.content}\nPasst das so? (ja/nein)")
            return {"playbook_state": pstate, "step_data": turn, "chat_state": "waiting_for_user"}

        reply = "" if turn.user_message_consumed else last_user_text(state.messages)
        turn.user_message_consumed = True
        if _YES.search(reply) and not _NO.search(reply):
            pstate.gate_status[gate.id] = "passed"
            pstate.awaiting_gate_id = None
            turn.turn_texts.append("Danke, das ist bestätigt.")
            return {"playbook_state": pstate, "step_data": turn, "chat_state": "in_progress"}
        if _NO.search(reply):
            pstate.awaiting_gate_id = None
            pstate.gate_status.pop(gate.id, None)
            reopened = set(gate.required_step_ids)
            pstate.completed_step_ids = [s for s in pstate.completed_step_ids if s not in reopened]
            pstate.shown_step_ids = [s for s in pstate.shown_step_ids if s not in reopened]
            turn.turn_texts.append("Verstanden, wir gehen die Phase noch einmal durch.")
            return {"playbook_state": pstate, "step_data": turn, "chat_state": "in_progress"}
        turn.turn_texts.append("Bitte antworten Sie mit ja oder nein: Passt die Zusammenfassung?")
        return {"playbook_state": pstate, "step_data": turn, "chat_state": "waiting_for_user"}
