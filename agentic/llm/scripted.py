"""Deterministic stand-in for a real model so the graph runs offline and in CI.

It reads the JSON payload the nodes send as ``user`` and answers with simple
keyword rules. It is intentionally dumb: it exists to exercise the
orchestration, not to judge language.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import LLMResponse

_UNCLEAR = ("weiß nicht", "weiss nicht", "keine ahnung", "später", "egal", "hmm", "don't know")
_QUESTION_STARTS = ("wie ", "was ", "warum ", "wieso ", "wozu ", "how ", "what ", "why ")


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class ScriptedLLM:
    fail_on: Set[str] = field(default_factory=set)
    calls: List[Tuple[str, int, int]] = field(default_factory=list)
    model: str = "scripted"

    async def complete(
        self,
        *,
        purpose: str,
        system: str,
        user: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        if purpose in self.fail_on:
            raise RuntimeError(f"scripted outage for purpose={purpose}")
        payload = json.loads(user)
        handler = getattr(self, f"_{purpose}")
        content = handler(payload)
        rendered = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        response = LLMResponse(
            content=content,
            model=self.model,
            input_tokens=_tokens(system) + _tokens(user),
            output_tokens=_tokens(rendered),
        )
        self.calls.append((purpose, response.input_tokens, response.output_tokens))
        return response

    @staticmethod
    def _intent(p: Dict[str, Any]) -> Dict[str, Any]:
        text = (p.get("user_text") or "").strip().lower()
        if not text:
            return {"kind": "proceed", "confidence": 1.0, "reason": "empty message"}
        if text.endswith("?") or text.startswith(_QUESTION_STARTS):
            return {"kind": "howto_or_meta", "confidence": 0.9, "reason": "question form"}
        return {"kind": "answer_to_active_step", "confidence": 0.8, "reason": "statement"}

    @staticmethod
    def _answer_check(p: Dict[str, Any]) -> Dict[str, Any]:
        text = (p.get("user_message") or "").strip()
        lowered = text.lower()
        step = p.get("step") or {}
        options = [o.lower() for o in step.get("options") or []]
        if any(marker in lowered for marker in _UNCLEAR) or lowered.endswith("?"):
            answered = False
        elif options:
            answered = any(opt in lowered.split() for opt in options)
        else:
            answered = len(text) >= 3
        return {
            "answered": answered,
            "confidence": 0.9 if answered else 0.85,
            "summary": text,
            "missing": [] if answered else [step.get("objective", "Antwort")],
        }

    @staticmethod
    def _dialog(p: Dict[str, Any]) -> str:
        mode = p.get("mode")
        prompt = (p.get("step") or {}).get("prompt", "")
        if mode == "open_step":
            research = p.get("research")
            if research:
                return f"{prompt} {research['name']}, {research['register']}, Sitz {research['seat']}."
            return prompt
        if mode == "acknowledge":
            return "Danke, notiert."
        if mode == "ask_missing":
            return f"Mir fehlt noch: {', '.join(p.get('missing') or [])}. {prompt}"
        if mode == "excursion":
            return f"Kurz zu Ihrer Frage: Wir erfassen das für den Projektsteckbrief. Zurück zur offenen Frage: {prompt}"
        return prompt

    @staticmethod
    def _gate_summary(p: Dict[str, Any]) -> str:
        parts = [f"{a['title']}: {a['summary']}" for a in p.get("answers") or []]
        return "Zusammenfassung: " + "; ".join(parts)
