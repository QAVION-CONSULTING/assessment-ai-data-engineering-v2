"""Chat with the onboarding agent in the terminal: ``uv run python -m agentic.cli``."""

import asyncio
import uuid

from .engine import OnboardingEngine


async def main() -> None:
    engine = OnboardingEngine()
    conversation_id = str(uuid.uuid4())
    for text in await engine.start(conversation_id, user_id="cli"):
        print(f"assistant> {text}")
    while True:
        try:
            user_text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_text in {"/quit", "/exit"}:
            break
        if user_text == "/usage":
            print(engine.usage.totals())
            continue
        for text in await engine.turn(conversation_id, user_text):
            print(f"assistant> {text}")


if __name__ == "__main__":
    asyncio.run(main())
