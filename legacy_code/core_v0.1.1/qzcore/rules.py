
import json
from pathlib import Path

def load_rules(path=None):
    if path is None:
        path = Path(__file__).resolve().parents[1] / "rules_config.json"
    return json.loads(Path(path).read_text(encoding="utf-8"))
