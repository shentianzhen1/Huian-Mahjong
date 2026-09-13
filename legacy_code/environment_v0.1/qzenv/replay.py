
import json
from pathlib import Path
from .actions import Action
from .events import Event

def save_events_jsonl(events, path):
    path = Path(path)
    with path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")

def load_events_jsonl(path):
    """
    读取原始事件字典。
    V0.1 暂不做完整 replay 重放，因为最终 Rules 尚未锁定。
    """
    out = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if line:
                out.append(json.loads(line))
    return out
