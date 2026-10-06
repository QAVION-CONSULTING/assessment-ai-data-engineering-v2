"""Token and cost accounting per conversation turn.

Spans form a tree (turn -> node -> llm call). The report is what we bill
clients on, so totals must match what the providers charge us.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional

from utils import settings


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cost_usd += other.cost_usd


@dataclass
class Span:
    name: str
    parent: Optional["Span"] = None
    usage: Usage = field(default_factory=Usage)
    children: List["Span"] = field(default_factory=list)


def _price(model: str) -> Dict[str, float]:
    prices = settings.llm.prices
    entry = prices.get(model) or prices.get("scripted")
    return {"input": float(entry["input"]), "output": float(entry["output"])}


class UsageTracker:
    def __init__(self) -> None:
        self.roots: List[Span] = []
        self._stack: List[Span] = []

    @contextmanager
    def span(self, name: str) -> Iterator[Span]:
        parent = self._stack[-1] if self._stack else None
        node = Span(name=name, parent=parent)
        if parent is None:
            self.roots.append(node)
        else:
            parent.children.append(node)
        self._stack.append(node)
        try:
            yield node
        finally:
            self._stack.pop()

    def record(self, *, model: str, input_tokens: int, output_tokens: int) -> None:
        price = _price(model)
        call = Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=(input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000,
        )
        # Roll the call up into every open span so each span shows its subtree.
        for open_span in self._stack:
            open_span.usage.add(call)

    def totals(self) -> Usage:
        total = Usage()
        for span in self._walk():
            total.add(span.usage)
        return total

    def by_name(self) -> Dict[str, Usage]:
        out: Dict[str, Usage] = {}
        for span in self._walk():
            out.setdefault(span.name, Usage()).add(span.usage)
        return out

    def _walk(self) -> Iterator[Span]:
        pending = list(self.roots)
        while pending:
            span = pending.pop()
            yield span
            pending.extend(span.children)


class TrackedLLM:
    """Wraps any LLMClient so every call is recorded under a span named after its purpose."""

    def __init__(self, inner, tracker: UsageTracker) -> None:
        self._inner = inner
        self._tracker = tracker

    async def complete(self, *, purpose: str, **kwargs):
        with self._tracker.span(f"llm.{purpose}"):
            response = await self._inner.complete(purpose=purpose, **kwargs)
            self._tracker.record(
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
            return response
