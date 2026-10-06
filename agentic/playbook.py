"""Playbook skeleton (what to ask) and playbook state (how far a conversation got)."""

import json
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PLAYBOOK_DIR = Path(__file__).with_name("playbooks")


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ordinal: int
    title: str
    prompt: str
    objective: str
    success_criteria: List[str] = Field(default_factory=list)
    options: List[str] = Field(default_factory=list)
    uses_research: bool = False


class Gate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    required_step_ids: List[str]


class Phase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ordinal: int
    title: str
    steps: List[Step]
    gate_id: Optional[str] = None


class Playbook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    language: str = "de"
    phases: List[Phase]
    gates: List[Gate] = Field(default_factory=list)

    def ordered_steps(self) -> List[Step]:
        return [
            step
            for phase in sorted(self.phases, key=lambda p: p.ordinal)
            for step in sorted(phase.steps, key=lambda s: s.ordinal)
        ]

    def find_phase(self, phase_id: Optional[str]) -> Optional[Phase]:
        return next((p for p in self.phases if p.id == phase_id), None)

    def find_step(self, step_id: Optional[str]) -> Optional[Step]:
        return next((s for s in self.ordered_steps() if s.id == step_id), None)

    def find_gate(self, gate_id: Optional[str]) -> Optional[Gate]:
        return next((g for g in self.gates if g.id == gate_id), None)

    def phase_of(self, step_id: str) -> Phase:
        for phase in self.phases:
            if any(s.id == step_id for s in phase.steps):
                return phase
        raise KeyError(step_id)


class PlaybookState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    playbook_version: str
    active_phase_id: str
    active_step_id: Optional[str] = None
    shown_step_ids: List[str] = Field(default_factory=list)
    completed_step_ids: List[str] = Field(default_factory=list)
    answers: Dict[str, Dict[str, object]] = Field(default_factory=dict)
    gate_status: Dict[str, Literal["pending", "passed"]] = Field(default_factory=dict)
    awaiting_gate_id: Optional[str] = None

    @classmethod
    def start(cls, playbook: Playbook) -> "PlaybookState":
        first_phase = min(playbook.phases, key=lambda p: p.ordinal)
        return cls(playbook_version=playbook.version, active_phase_id=first_phase.id)


def load_playbook(name: str) -> Playbook:
    path = PLAYBOOK_DIR / f"{name}.json"
    return Playbook.model_validate(json.loads(path.read_text(encoding="utf-8")))
