import json
import importlib.resources
from . import data

def load_indicators() -> list[str]:
    text = importlib.resources.read_text(data, "indicators.json")
    return json.loads(text)

def is_challenge_body(body: str) -> bool:
    if not body:
        return False
    body_lower = body.lower()
    indicators = load_indicators()
    return any(indicator in body_lower for indicator in indicators)
