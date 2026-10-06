from typing import Any, Dict, Generic, List, Optional, TypedDict, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)

class BaseAgentState(BaseModel, Generic[T]):
    """
    Pydantic BaseModel state shared across LangGraph nodes.
    This is the state model that should be used for all services.
    """

    conversation_id: str
    user_id: str
    company_id: Optional[str] = None
    # Trusted correlation — propagate from AuthenticatedIdentityContext; do not invent per-node.
    request_id: Optional[str] = None
    server_request_id: Optional[str] = None
    invocation_id: Optional[str] = None
    messages: List[Dict[str, Any]]
    step_data: T
    next_node: Optional[str] = None
    chat_state: Optional[str] = None
    language: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

# For backwards compatibility until everything has been refactored
class AgentState(TypedDict, total=False):
    """Previous TypedDict state shared across LangGraph nodes."""

    conversation_id: str
    user_id: str
    company_id: Optional[str]
    request_id: Optional[str]
    server_request_id: Optional[str]
    invocation_id: Optional[str]
    messages: List[Dict[str, Any]]
    step_data: Dict[str, Any]
    next_node: Optional[str]
    chat_state: Optional[str]
    language: Optional[str]
    metadata: Dict[str, Any]