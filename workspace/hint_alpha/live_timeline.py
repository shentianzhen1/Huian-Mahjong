"""Read-only display of evidence events; never infer missing game actions."""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone


def known(value):
    if value is None or value == "" or value == "UNKNOWN":
        return "未知"
    if isinstance(value, (tuple, list)):
        return " / ".join(known(item) for item in value) if value else "未知"
    return str(value)


def event_row(event):
    payload = event.get("payload") or {}
    kind = event.get("kind", "UNKNOWN")
    stamp = event.get("at")
    try:
        stamp = datetime.fromisoformat(stamp).astimezone(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
    except (TypeError, ValueError):
        stamp = "未知"
    hand = actor = tile = "未知"
    status = "未验证观察"
    title = {
        "SESSION_STARTED": "会话开始", "CAPTURE_STARTED": "采集开始",
        "MANUAL_ENTRY_STARTED": "人工输入开始", "CURRENT_SNAPSHOT_HINT": "牌桌观察 / 向听辅助",
        "PUBLIC_STATE": "状态栏观察", "BLACK_FRAME": "黑屏，动作未知",
        "CAPTURE_ERROR": "采集错误，动作未知", "RUNTIME_VISION_ERROR": "识别错误，动作未知",
        "FRAME_SAVED": "截图保存", "SETTLEMENT_PAGE": "结算页保存，结果待审阅",
        "HAND_RECORDING_SAVED": "录像保存", "UNKNOWN_RULE": "规则未知",
        "MANUAL_HAND_INPUT": "人工手牌输入", "MANUAL_SCORE_INPUT": "人工分数记录",
    }.get(kind, kind)
    detail = json.dumps(payload, ensure_ascii=False, default=str)
    if kind == "PUBLIC_STATE":
        observation = payload.get("observation") or {}
        issues = observation.get("issues") or ()
        hand = known(observation.get("hand_number")) if not issues else "未知"
        scores = observation.get("score_pair")
        valid_scores = (isinstance(scores, (list, tuple)) and len(scores) == 2
            and all(type(x) is int and 0 <= x <= 2000 for x in scores) and sum(scores) == 2000)
        detail = (f"比分={known(scores) if valid_scores and not issues else '未知'}；"
            f"余牌={known(observation.get('remaining_tiles')) if not issues else '未知'}；"
            f"动作=未知；问题={known(issues)}")
    elif kind == "CURRENT_SNAPSHOT_HINT":
        accepted = payload.get("display_allowed") is True
        tile = known(payload.get("gold_tile")) if accepted else "未知"
        status = "实验观察，非确认动作" if accepted else "未知 / 已停用提示"
        detail = (f"手牌={known(payload.get('hand')) if accepted else '未知'}；"
            f"向听={known(payload.get('shanten')) if accepted else '未知'}；"
            f"动作=未知；问题={known(payload.get('issues'))}")
    return (known(stamp), hand, actor, title, tile, status, detail)


class EvidenceTail:
    """Bounded append-only JSONL reader, retaining incomplete writes for next poll."""
    def __init__(self):
        self.path = None
        self.offset = 0
        self.pending = b""

    def read(self, path):
        path = Path(path)
        if path != self.path or (path.exists() and path.stat().st_size < self.offset):
            self.path, self.offset, self.pending = path, 0, b""
        if not path.exists():
            return []
        with path.open("rb") as stream:
            stream.seek(self.offset)
            chunk = stream.read(131072)
            self.offset = stream.tell()
        lines = (self.pending + chunk).split(b"\n")
        self.pending = lines.pop()
        result = []
        for line in lines:
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    result.append(event)
            except (ValueError, UnicodeDecodeError):
                result.append({"kind": "UNKNOWN", "payload": {"error": "流水记录无法解析"}})
        return result
