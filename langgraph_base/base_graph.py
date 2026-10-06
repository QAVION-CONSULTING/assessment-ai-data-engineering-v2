import json
from abc import ABC
from typing import Any, Callable, Dict, Iterable, Optional

from langgraph.graph import END, StateGraph
from pydantic import BaseModel
from typing_extensions import Type

from utils import get_logger

from .state import BaseAgentState

logger = get_logger(__name__)


class AgenticGraph(ABC):
    """Base helper for compiling LangGraph workflows from declarative configs.

    Design goals:
    - Build `StateGraph[AgentState]` instances from JSON configs.
    - Stay generic and reusable across different domain agents.
    - Support both:
      - legacy subclass-based handlers (methods on `self`)
      - registry-based handlers/routers passed in from the outside
        so that node logic can live in plain modules/functions.
    """

    def __init__(
        self,
        config_path: str,
        *,
        schema: Type[BaseModel],
        handlers: Optional[Dict[str, Callable[..., Any]]] = None,
        routers: Optional[Dict[str, Callable[..., Any]]] = None,
        tool_registry: Optional[Dict[str, Any]] = None,
        checkpointer: Any = None,
    ):
        # Optional registries for node handlers and routers.
        # If not provided, we fall back to looking up attributes on `self`,
        # which keeps existing subclass-based graphs working.

        if schema is BaseAgentState:
            raise TypeError(
                'BaseAgentState is generic and cannot be used directly. '
                'Pass a service-specific subclass with typed step_data.'
            )
        self.state_schema = schema

        self.handlers: Dict[str, Callable[..., Any]] = handlers or {}
        self.routers: Dict[str, Callable[..., Any]] = routers or {}

        self.tool_registry = tool_registry or {}
        self.checkpointer = checkpointer
        self.config = self._load_config(config_path)
        self.node_configs = {
            node_cfg["name"]: node_cfg for node_cfg in self.config.get("nodes", [])
        }
        self.workflow = self._build_graph()

    def _load_config(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as config_file:
            return json.load(config_file)

    def _build_graph(self):
        graph_builder = StateGraph(self.state_schema)

        # Register nodes declared in config
        self._register_nodes(graph_builder)

        # Set entry point
        graph_builder.set_entry_point(self.config["entry_point"])

        # Static edges
        for edge in self.config.get("edges", []):
            graph_builder.add_edge(edge["source"], edge["target"])

        # Conditional edges
        for conditional in self.config.get("conditional_edges", []):
            router_name = conditional["router"]

            # Prefer an explicitly passed-in router, fall back to attribute lookup
            # on `self` for backward compatibility with subclass-based graphs.
            router = self.routers.get(router_name) or getattr(self, router_name)

            # Normalize special "__end__" sentinel from JSON config to LangGraph's END.
            raw_map: Dict[Any, Any] = conditional.get("path_map", {})
            normalized_map: Dict[Any, Any] = {}
            for key, target in raw_map.items():
                route_key = END if key == "__end__" else key
                route_target = END if target == "__end__" else target
                normalized_map[route_key] = route_target

            graph_builder.add_conditional_edges(
                conditional["source"],
                router,
                normalized_map,
            )

        return graph_builder.compile(checkpointer=self.checkpointer)

    def _register_nodes(self, graph_builder: StateGraph):
        """Registers node handlers defined in the JSON config."""
        for node_name, node_cfg in self.node_configs.items():
            handler_name = node_cfg.get("handler")
            if not handler_name:
                raise ValueError(f"Node '{node_name}' is missing a handler reference")

            # Prefer registry-based handlers if provided, otherwise fall back
            # to methods on `self` for existing subclass-based agents.
            handler = self.handlers.get(handler_name)
            if handler is None:
                handler = getattr(self, handler_name, None)

            if handler is None:
                raise AttributeError(
                    f"{self.__class__.__name__} is missing handler '{handler_name}'"
                )
            graph_builder.add_node(node_name, handler)

    # --- Helper API ----------------------------------------------------- #
    def get_node_config(self, node_name: str) -> Dict[str, Any]:
        if node_name not in self.node_configs:
            raise KeyError(f"Unknown node '{node_name}'")
        return self.node_configs[node_name]

    def get_node_tools(self, node_name: str) -> Iterable[Any]:
        node_cfg = self.get_node_config(node_name)
        tool_ids = node_cfg.get("tools", [])
        for tool in tool_ids:
            yield self._resolve_tool(tool)

    def _resolve_tool(self, tool_identifier: Any) -> Any:
        if isinstance(tool_identifier, str):
            if tool_identifier not in self.tool_registry:
                raise KeyError(f"Tool '{tool_identifier}' is not registered")
            return self.tool_registry[tool_identifier]
        return tool_identifier

    # --- Generic routers ------------------------------------------------ #
    def route_by_state(self, state: BaseAgentState) -> str:
        """
        Generic router that maps a state field (e.g. chat_state) to the
        next node name, according to a `state_router` config section:

        \"\"\"json
        {
          "state_router": {
            "field": "chat_state",
            "default": "greeting",
            "map": {
              "greeting": "greeting",
              "problem_capture": "problem_capture_agent",
              "deep_research": "deep_research",
              "questions": "await_questions",
              "completed": "completed"
            }
          }
        }
        \"\"\"
        """
        cfg: Dict[str, Any] = self.config.get("state_router") or {}
        field = cfg.get("field", "chat_state")
        default = cfg.get("default", "greeting")        
        value = (getattr(state, field, None) or default or "").lower()
        mapping: Dict[str, str] = cfg.get("map") or {}

        # When using dict-style conditional edges, LangGraph expects the router
        # to return the *key* from `path_map`, not the target node name.
        # Keys correspond to logical states (e.g. "problem_capture"), while
        # values map to concrete node names (e.g. "problem_capture_agent").
        #
        # We treat unknown values and "__end__" as graph termination (END).
        if value not in mapping or value == "__end__":
            return END

        return value
