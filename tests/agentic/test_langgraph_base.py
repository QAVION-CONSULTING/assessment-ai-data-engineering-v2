import pytest

from langgraph_base import AgenticGraph, BaseAgentState


class _Graph(AgenticGraph):
    pass


def test_generic_base_state_is_rejected(tmp_path):
    config = tmp_path / "graph.json"
    config.write_text('{"entry_point": "a", "nodes": []}', encoding="utf-8")
    with pytest.raises(TypeError):
        _Graph(str(config), schema=BaseAgentState)
