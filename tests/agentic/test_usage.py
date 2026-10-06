import uuid

from agentic.engine import OnboardingEngine
from agentic.llm import ScriptedLLM
from agentic.usage import UsageTracker


async def test_turn_usage_matches_provider_usage():
    llm = ScriptedLLM()
    engine = OnboardingEngine(llm=llm)
    cid = str(uuid.uuid4())
    await engine.start(cid, user_id="test")
    await engine.turn(cid, "Müller Maschinenbau GmbH")

    totals = engine.usage.totals()

    assert totals.input_tokens == sum(call[1] for call in llm.calls)
    assert totals.output_tokens == sum(call[2] for call in llm.calls)


def test_cost_uses_configured_prices():
    tracker = UsageTracker()
    with tracker.span("llm.dialog"):
        tracker.record(model="openai/gpt-5", input_tokens=1_000_000, output_tokens=100_000)

    assert round(tracker.totals().cost_usd, 4) == 2.25
