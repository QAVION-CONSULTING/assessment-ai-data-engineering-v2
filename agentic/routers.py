"""Pure routers. No side effects."""

from .state import OnboardingState


def route_after_planner(state: OnboardingState) -> str:
    decision = state.step_data.planner_decision
    if decision is None or decision.action == "finish":
        return "__end__"
    if decision.action == "review_gate":
        return "gate"
    return "dialog"


def route_after_dialog(state: OnboardingState) -> str:
    # Keep planning until the assistant has asked the user something.
    return "__end__" if state.chat_state == "waiting_for_user" else "planner"


def route_after_gate(state: OnboardingState) -> str:
    return "__end__" if state.chat_state == "waiting_for_user" else "planner"
