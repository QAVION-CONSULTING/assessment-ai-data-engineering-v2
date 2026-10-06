from typing import Any, Dict, List


def last_user_text(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "").strip()
    return ""


def recent_turns(messages: List[Dict[str, Any]], limit: int = 6, max_chars: int = 800):
    return [
        {"role": m.get("role"), "content": str(m.get("content") or "")[:max_chars]}
        for m in messages[-limit:]
    ]
