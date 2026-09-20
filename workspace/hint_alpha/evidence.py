"""Structured evidence sessions for live internal testing."""
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import uuid

from huian.rules import DEFAULT_RULE_SNAPSHOT
from workspace.ai import CURRENT_AGENT_NAME, CURRENT_AGENT_VERSION


def _json_default(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _write_json(path, value):
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )


class EvidenceSession:
    """Append-only session log with RuleSnapshot/Agent provenance."""

    def __init__(self, root, *, metadata=None, session_id=None):
        self.root = Path(root)
        self.session_id = session_id or (
            datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        )
        self.path = self.root / self.session_id
        self.frames_path = self.path / "frames"
        self.recordings_path = self.path / "recordings"
        self.path.mkdir(parents=True, exist_ok=False)
        self.frames_path.mkdir()
        self.recordings_path.mkdir()
        self.events_path = self.path / "events.jsonl"
        self._lock = threading.Lock()
        self._sequence = 0
        self._closed = False
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.manifest = {
            "schema_version": 1,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "mode": "HINT_ALPHA_V0_1",
            "executor_enabled": False,
            "agent": {
                "name": CURRENT_AGENT_NAME,
                "version": CURRENT_AGENT_VERSION,
            },
            "rule_snapshot": DEFAULT_RULE_SNAPSHOT.to_manifest(),
            "metadata": dict(metadata or {}),
        }
        _write_json(self.path / "session.json", self.manifest)
        self.mark("SESSION_STARTED", {"executor_enabled": False})

    def mark(self, kind, payload=None, *, source=None):
        if not isinstance(kind, str) or not kind:
            raise ValueError("kind must be a nonempty string")
        with self._lock:
            if self._closed:
                raise RuntimeError("evidence session is closed")
            self._sequence += 1
            event = {
                "seq": self._sequence,
                "at": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                "payload": dict(payload or {}),
                "source": dict(source or {}),
                "rule_snapshot_id": DEFAULT_RULE_SNAPSHOT.fingerprint,
                "agent_version": CURRENT_AGENT_VERSION,
            }
            with self.events_path.open("a", encoding="utf-8", newline="\n") as output:
                output.write(
                    json.dumps(
                        event,
                        ensure_ascii=False,
                        sort_keys=True,
                        default=_json_default,
                    )
                    + "\n"
                )
                output.flush()
            return event

    def save_frame(self, image, label, *, source=None, payload=None):
        if image is None:
            raise ValueError("image is required")
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(label))
        name = f"{self._sequence + 1:05d}_{safe or 'frame'}.png"
        path = self.frames_path / name
        image.save(path, format="PNG")
        self.mark(
            "FRAME_SAVED",
            {"label": str(label), "path": str(path.relative_to(self.path)), **dict(payload or {})},
            source=source,
        )
        return path

    def mark_unknown(self, rule_ids, *, payload=None, source=None):
        ids = tuple(dict.fromkeys(rule_ids or ()))
        if not ids:
            raise ValueError("rule_ids must not be empty")
        return self.mark(
            "UNKNOWN_RULE",
            {"rule_ids": list(ids), **dict(payload or {})},
            source=source,
        )

    def mark_feedback(self, category, *, payload=None, source=None):
        if category not in ("RECOGNITION_ERROR", "AI_ADVICE_ERROR", "RULE_EVIDENCE"):
            raise ValueError("unsupported feedback category")
        return self.mark(category, payload, source=source)

    def close(self, reason="normal"):
        with self._lock:
            if self._closed:
                return None
            self._closed = True
            completion = {
                "schema_version": 1,
                "session_id": self.session_id,
                "started_at": self.started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "events_written": self._sequence,
                "reason": str(reason),
                "rule_snapshot_id": DEFAULT_RULE_SNAPSHOT.fingerprint,
                "agent_version": CURRENT_AGENT_VERSION,
            }
            _write_json(self.path / "completion.json", completion)
            return completion
