"""Local, non-overwriting evaluation artifacts and verified deterministic replay."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

from workspace.ai import BaselineAgent
from .core import RandomAgent, Simulator, SimulatorConfig
from .evaluation import make_hand_summary, run_many_normal_hands


AGENTS = {"random": RandomAgent, "baseline": BaselineAgent}
SCHEMA_VERSION = 1


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_value(value):
    return json.loads(_canonical(value))


def event_digest(events):
    return hashlib.sha256(_canonical(events).encode("utf-8")).hexdigest()


def source_digest():
    """Hash runtime sources with normalized newlines, excluding tests/media."""
    root = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for folder in ("huian", "mahjong_framework", "workspace/ai",
                   "workspace/simulator", "legacy_code"):
        for path in sorted((root / folder).rglob("*.py")):
            relative = path.relative_to(root)
            if "tests" in relative.parts or "__pycache__" in relative.parts:
                continue
            digest.update(relative.as_posix().encode("utf-8") + b"\0")
            digest.update(path.read_text(encoding="utf-8").encode("utf-8") + b"\0")
    return digest.hexdigest()


def runtime_id():
    return {"implementation": sys.implementation.name, "version": platform.python_version()}


def _write_new_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _validate_parameters(seeds, agent_names, max_steps, swap_seats, dealer):
    if not seeds or any(type(seed) is not int for seed in seeds):
        raise ValueError("seeds must be a nonempty list of integers")
    if len(agent_names) != 2 or any(name not in AGENTS for name in agent_names):
        raise ValueError("Use two registered agents: random / baseline")
    if type(max_steps) is not int or max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    if type(swap_seats) is not bool:
        raise ValueError("swap_seats must be boolean")
    if type(dealer) is not int or dealer not in (0, 1):
        raise ValueError("dealer must be seat 0 or 1")


def run_saved_evaluation(output_dir, seeds, *, agent_names=("random", "baseline"),
                         max_steps=1000, swap_seats=False, dealer=0, on_progress=None):
    """Create a NEW directory; preserve flushed hand records if interrupted.

    run.json is immutable input metadata. completion.json records whether the
    entire batch finished. summary.json is written only for a complete batch.
    Each hand record includes its event digest so replay checks decisions too.
    """
    seeds, agent_names = tuple(seeds), tuple(agent_names)
    _validate_parameters(seeds, agent_names, max_steps, swap_seats, dealer)
    if on_progress is not None and not callable(on_progress):
        raise ValueError("on_progress must be callable")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_digest": source_digest(), "runtime": runtime_id(),
        "simulation_only": True, "simulator_config": asdict(SimulatorConfig()),
        "parameters": {"seeds": seeds, "agent_names": agent_names,
                       "max_steps": max_steps, "swap_seats": swap_seats, "dealer": dealer},
    }
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=False)
    _write_new_json(directory / "run.json", manifest)
    written = 0
    total = len(seeds) * (2 if swap_seats else 1)
    try:
        with (directory / "hands.jsonl").open("x", encoding="utf-8", newline="\n") as output:
            def record(summary, result):
                nonlocal written
                if not result.simulation_only:
                    raise ValueError("Saved evaluation only accepts simulation-only results")
                item = {"hand_index": written, "summary": asdict(summary),
                        "event_digest": event_digest(result.events)}
                output.write(_canonical(item) + "\n")
                output.flush()
                written += 1
                if on_progress is not None:
                    on_progress(written, total, summary)

            report = run_many_normal_hands(
                seeds, agent_factories=tuple(AGENTS[name] for name in agent_names),
                max_steps=max_steps, swap_seats=swap_seats, dealer=dealer, on_hand=record)
        _write_new_json(directory / "summary.json", report.to_dict())
    except BaseException as exc:
        _write_new_json(directory / "completion.json", {
            "status": "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
            "hands_written": written, "hands_requested": total,
            "error_type": type(exc).__name__,
        })
        raise
    _write_new_json(directory / "completion.json", {
        "status": "completed", "hands_written": written, "hands_requested": total})
    return report


def replay_saved_hand(report_dir, hand_index):
    """Rerun one recorded hand and verify summary, state hashes and decisions.

    Only built-in agent names are read from the manifest; no import paths or
    executable code are accepted. Returns the full trace after verification.
    It can replay a flushed hand from an interrupted batch.
    """
    if type(hand_index) is not int or hand_index < 0:
        raise ValueError("hand_index must be a nonnegative integer")
    directory = Path(report_dir)
    manifest = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Evaluation manifest must be a JSON object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported evaluation schema")
    if manifest.get("simulation_only") is not True:
        raise ValueError("Only simulation-only evaluations may be replayed")
    if manifest.get("simulator_config") != asdict(SimulatorConfig()):
        raise ValueError("Unsupported simulator profile")
    if manifest.get("runtime") != runtime_id():
        raise ValueError("Python runtime differs from the recorded run")
    if manifest.get("source_digest") != source_digest():
        raise ValueError("Runtime sources differ; use the recorded code before replay")
    params = manifest["parameters"]
    seeds, names = params["seeds"], params["agent_names"]
    _validate_parameters(seeds, names, params["max_steps"], params["swap_seats"], params["dealer"])
    record = None
    with (directory / "hands.jsonl").open(encoding="utf-8") as lines:
        for index, line in enumerate(lines):
            if index == hand_index:
                record = json.loads(line)
                break
    if record is None:
        raise ValueError("hand_index has no saved hand record")
    if record.get("hand_index") != hand_index:
        raise ValueError("Saved hand index does not match its record")
    pair_index, swap_number = divmod(hand_index, 2 if params["swap_seats"] else 1)
    if pair_index >= len(seeds):
        raise ValueError("Saved hand index exceeds requested seeds")
    seed, swapped = seeds[pair_index], bool(swap_number)
    identities = (1, 0) if swapped else (0, 1)
    identity_agents = [AGENTS[name](seed=seed * 2 + i) for i, name in enumerate(names)]
    agents = tuple(identity_agents[i] for i in identities)
    result = Simulator().run_normal_hand(
        seed=seed, agents=agents, max_steps=params["max_steps"], dealer=params["dealer"])
    summary = make_hand_summary(
        result, seed=seed, swapped=swapped,
        agent_names=tuple(type(agent).__name__ for agent in agents), pair_index=pair_index)
    if _json_value(asdict(summary)) != record.get("summary"):
        raise ValueError("Replay summary differs from the saved hand")
    digest = event_digest(result.events)
    if digest != record.get("event_digest"):
        raise ValueError("Replay decision/event trace differs from the saved hand")
    return {"schema_version": SCHEMA_VERSION, "verified": True,
            "hand_index": hand_index, "summary": asdict(summary),
            "event_digest": digest, "events": result.events}


def save_replay(output_path, payload):
    """Write a verified trace exclusively; an existing file is never replaced."""
    if payload.get("verified") is not True:
        raise ValueError("Only verified replay traces may be saved")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_new_json(path, payload)
