"""Fast on-disk evaluation/replay checks using a one-action hand budget."""
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from workspace.simulator.artifacts import (
    event_digest, replay_saved_hand, run_saved_evaluation, save_replay,
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


class SimulatorArtifactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_temp = TemporaryDirectory()
        cls.addClassCleanup(cls.fixture_temp.cleanup)
        cls.fixture = Path(cls.fixture_temp.name) / "saved"
        cls.report = run_saved_evaluation(
            cls.fixture, [2], max_steps=1, swap_seats=True)

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.saved = self.root / "saved"
        shutil.copytree(self.fixture, self.saved)

    def records(self):
        return [json.loads(line) for line in
                (self.saved / "hands.jsonl").read_text(encoding="utf-8").splitlines()]

    def write_records(self, records):
        (self.saved / "hands.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

    def test_saved_batch_and_swapped_hand_replay(self):
        self.assertEqual({path.name for path in self.saved.iterdir()},
                         {"run.json", "hands.jsonl", "summary.json", "completion.json"})
        self.assertEqual(read_json(self.saved / "completion.json"), {
            "status": "completed", "hands_written": 2, "hands_requested": 2})
        self.assertEqual(read_json(self.saved / "summary.json"),
                         json.loads(json.dumps(self.report.to_dict())))
        records = self.records()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["summary"]["agents"], ["RandomAgent", "BaselineAgent"])
        self.assertEqual(records[1]["summary"]["agents"], ["BaselineAgent", "RandomAgent"])
        for index, record in enumerate(records):
            with self.subTest(index=index):
                replay = replay_saved_hand(self.saved, index)
                self.assertTrue(replay["verified"])
                self.assertEqual(replay["summary"]["swapped"], bool(index))
                self.assertEqual(replay["event_digest"], record["event_digest"])
                self.assertEqual(event_digest(replay["events"]), record["event_digest"])
                self.assertEqual(json.loads(json.dumps(replay["summary"])), record["summary"])

    def test_existing_directory_is_never_overwritten(self):
        before = {path.name: path.read_bytes() for path in self.saved.iterdir()}
        with self.assertRaises(FileExistsError):
            run_saved_evaluation(self.saved, [2], max_steps=1)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.saved.iterdir()})

    def test_replay_export_is_verified_and_never_overwrites(self):
        target = self.root / "replays" / "hand.json"
        replay = replay_saved_hand(self.saved, 1)
        save_replay(target, replay)
        original = target.read_bytes()
        self.assertEqual(read_json(target)["event_digest"], replay["event_digest"])
        with self.assertRaises(FileExistsError):
            save_replay(target, replay)
        self.assertEqual(target.read_bytes(), original)
        unverified = self.root / "unverified.json"
        with self.assertRaises(ValueError):
            save_replay(unverified, {"verified": False})
        self.assertFalse(unverified.exists())

    def test_modified_summary_and_event_digest_are_rejected(self):
        original = self.records()
        modified = json.loads(json.dumps(original))
        modified[0]["summary"]["steps"] += 1
        self.write_records(modified)
        with self.assertRaisesRegex(ValueError, "summary"):
            replay_saved_hand(self.saved, 0)
        modified = json.loads(json.dumps(original))
        modified[0]["event_digest"] = "0" * 64
        self.write_records(modified)
        with self.assertRaisesRegex(ValueError, "trace"):
            replay_saved_hand(self.saved, 0)

    def test_different_sources_or_runtime_are_rejected(self):
        path = self.saved / "run.json"
        original = read_json(path)
        for key, value, message in (
            ("source_digest", "0" * 64, "sources"),
            ("runtime", {"implementation": "different", "version": "0"}, "runtime"),
        ):
            with self.subTest(key=key):
                modified = dict(original)
                modified[key] = value
                write_json(path, modified)
                with self.assertRaisesRegex(ValueError, message):
                    replay_saved_hand(self.saved, 0)

    def test_interrupted_batch_preserves_flushed_hand_and_can_replay(self):
        interrupted = self.root / "interrupted"
        progress = []

        def interrupt(written, total, summary):
            progress.append((written, total, summary.seed))
            # Confirm the record is already on disk before the callback returns.
            self.assertEqual(len((interrupted / "hands.jsonl").read_text(
                encoding="utf-8").splitlines()), written)
            raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            run_saved_evaluation(interrupted, [2, 3], max_steps=1,
                                 swap_seats=True, on_progress=interrupt)
        self.assertEqual(progress, [(1, 4, 2)])
        self.assertFalse((interrupted / "summary.json").exists())
        self.assertEqual(read_json(interrupted / "completion.json"), {
            "status": "interrupted", "hands_written": 1, "hands_requested": 4,
            "error_type": "KeyboardInterrupt"})
        self.assertTrue(replay_saved_hand(interrupted, 0)["verified"])
        with self.assertRaisesRegex(ValueError, "no saved hand"):
            replay_saved_hand(interrupted, 1)

    def test_invalid_inputs_leave_no_output_directory(self):
        cases = (
            {"seeds": []}, {"seeds": [True]}, {"seeds": ["2"]},
            {"agent_names": ("random",)},
            {"agent_names": ("random", "unregistered")},
            {"max_steps": 0}, {"max_steps": True}, {"swap_seats": 1},
            {"dealer": 2}, {"on_progress": False},
        )
        for index, changes in enumerate(cases):
            with self.subTest(changes=changes):
                target = self.root / f"invalid-{index}"
                parameters = {"seeds": [2], "max_steps": 1, **changes}
                with self.assertRaises(ValueError):
                    run_saved_evaluation(target, **parameters)
                self.assertFalse(target.exists())

    def test_invalid_or_missing_hand_index_is_rejected(self):
        for index in (-1, True, "0", 2):
            with self.subTest(index=index), self.assertRaises(ValueError):
                replay_saved_hand(self.saved, index)
        records = self.records()
        records[0]["hand_index"] = 1
        self.write_records(records)
        with self.assertRaisesRegex(ValueError, "index does not match"):
            replay_saved_hand(self.saved, 0)


if __name__ == "__main__":
    unittest.main()
