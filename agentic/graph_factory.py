from pathlib import Path
from typing import Any, Callable, Dict

from langgraph_base import AgenticGraph

from .dialog import AnswerChecker, DialogExecutor
from .gate import GateReviewer
from .llm import LLMClient
from .planner import IntentClassifier, StepPlanner
from .routers import route_after_dialog, route_after_gate, route_after_planner
from .state import OnboardingState
from .tools import CompanyResearchTool

GRAPH_CONFIG_PATH = str(Path(__file__).with_name("graph_config.json"))


class OnboardingGraph(AgenticGraph):
    pass


def build_graph(*, llm: LLMClient, research: CompanyResearchTool) -> OnboardingGraph:
    planner = StepPlanner(IntentClassifier(llm))
    dialog = DialogExecutor(llm, AnswerChecker(llm), research)
    gate = GateReviewer(llm)

    async def run_step_planner(state: OnboardingState) -> Dict[str, Any]:
        decision = await planner.decide(state)
        return {"step_data": state.step_data.model_copy(update={"planner_decision": decision})}

    async def run_dialog_executor(state: OnboardingState) -> Dict[str, Any]:
        return await dialog.execute(state)

    async def run_gate_reviewer(state: OnboardingState) -> Dict[str, Any]:
        return await gate.execute(state)

    handlers: Dict[str, Callable[..., Any]] = {
        "run_step_planner": run_step_planner,
        "run_dialog_executor": run_dialog_executor,
        "run_gate_reviewer": run_gate_reviewer,
    }
    routers: Dict[str, Callable[..., Any]] = {
        "route_after_planner": route_after_planner,
        "route_after_dialog": route_after_dialog,
        "route_after_gate": route_after_gate,
    }
    return OnboardingGraph(
        GRAPH_CONFIG_PATH,
        schema=OnboardingState,
        handlers=handlers,
        routers=routers,
        tool_registry={"company_research": research},
    )
