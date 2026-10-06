import uuid

from agentic.engine import OnboardingEngine
from agentic.llm import ScriptedLLM


async def _started(llm: ScriptedLLM):
    engine = OnboardingEngine(llm=llm)
    conversation_id = str(uuid.uuid4())
    opening = await engine.start(conversation_id, user_id="test")
    return engine, conversation_id, opening


async def _complete_phase_one(engine, conversation_id):
    await engine.turn(conversation_id, "Müller Maschinenbau GmbH")
    await engine.turn(conversation_id, "ja")
    return await engine.turn(conversation_id, "Maschinenbau, rund 400 Mitarbeitende")


async def test_start_opens_first_step():
    _, _, opening = await _started(ScriptedLLM())
    assert opening == ["Wie lautet die vollständige Firmierung Ihres Unternehmens?"]


async def test_company_name_triggers_register_lookup():
    engine, cid, _ = await _started(ScriptedLLM())
    texts = await engine.turn(cid, "Müller Maschinenbau GmbH")
    assert texts[0] == "Danke, notiert."
    assert "HRB 48213" in texts[1]
    assert engine.conversation(cid).playbook_state.active_step_id == "s2_company_confirm"


async def test_phase_one_ends_at_gate():
    engine, cid, _ = await _started(ScriptedLLM())
    texts = await _complete_phase_one(engine, cid)
    assert texts[-1].endswith("Passt das so? (ja/nein)")
    assert engine.conversation(cid).playbook_state.awaiting_gate_id == "g1"


async def test_gate_confirmation_opens_next_phase():
    engine, cid, _ = await _started(ScriptedLLM())
    await _complete_phase_one(engine, cid)
    texts = await engine.turn(cid, "ja, passt")
    pstate = engine.conversation(cid).playbook_state
    assert pstate.gate_status["g1"] == "passed"
    assert pstate.active_step_id == "s4_main_goal"
    assert texts[-1].startswith("Welches Ziel")


async def test_side_question_returns_to_open_step():
    engine, cid, _ = await _started(ScriptedLLM())
    texts = await engine.turn(cid, "Wozu brauchen Sie das?")
    pstate = engine.conversation(cid).playbook_state
    assert len(texts) == 1
    assert texts[0].endswith("Wie lautet die vollständige Firmierung Ihres Unternehmens?")
    assert pstate.completed_step_ids == []


async def test_unclear_answer_asks_again_and_ends_the_turn():
    llm = ScriptedLLM()
    engine, cid, _ = await _started(llm)
    calls_before = len(llm.calls)

    texts = await engine.turn(cid, "weiß nicht, ehrlich gesagt")

    assert len(texts) == 1
    assert texts[0].startswith("Mir fehlt noch")
    assert engine.conversation(cid).playbook_state.completed_step_ids == []
    assert len(llm.calls) - calls_before <= 3


async def test_judge_outage_does_not_complete_the_step():
    engine, cid, _ = await _started(ScriptedLLM(fail_on={"answer_check"}))

    await engine.turn(cid, "Müller Maschinenbau GmbH")

    pstate = engine.conversation(cid).playbook_state
    assert "s1_company_name" not in pstate.completed_step_ids
    assert pstate.active_step_id == "s1_company_name"
