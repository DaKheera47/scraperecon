import json
import importlib.resources
from . import data

def load_signatures() -> dict:
    text = importlib.resources.read_text(data, "signatures.json")
    return json.loads(text)
