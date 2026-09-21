from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from .phase5e_holdout import _known_source_tokens, _source_is_known


class Phase5ESourceDisjointTests(unittest.TestCase):
    def test_known_tokens_include_truth_hashes_and_approved_label_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp)
            (dataset / "validation" / "holdout").mkdir(parents=True)

            full_hash = "a" * 64
            (dataset / "validation" / "geometry_ground_truth_v0_2.jsonl").write_text(
                json.dumps({
                    "source_sha256": full_hash,
                    "source_id": "src_1111222233334444",
                    "source_session": "session_5555666677778888",
                }) + "\n",
                encoding="utf-8",
            )
            (dataset / "validation" / "holdout" / "geometry_holdout_ground_truth_v0_2.jsonl").write_text(
                json.dumps({
                    "source_sha256": "b" * 64,
                    "source_id": "src_9999aaaabbbbcccc",
                    "source_session": "session_ddddeeeeffff0000",
                }) + "\n",
                encoding="utf-8",
            )
            (dataset / "labels.jsonl").write_text(
                "\n".join([
                    json.dumps({
                        "approved": True,
                        "source_id": "src_deadbeefcafebabe",
                        "source_session": "session_0123456789abcdef",
                    }),
                    json.dumps({
                        "approved": False,
                        "source_id": "src_shouldnotblock00",
                        "source_session": "session_shouldnotblock00",
                    }),
                ]) + "\n",
                encoding="utf-8",
            )

            tokens = _known_source_tokens(dataset)
            self.assertIn(full_hash, tokens)
            self.assertIn("deadbeefcafebabe", tokens)
            self.assertIn("0123456789abcdef", tokens)
            self.assertNotIn("shouldnotblock00", tokens)

    def test_prefix_match_blocks_anonymized_known_source(self) -> None:
        tokens = {"deadbeefcafebabe"}
        self.assertTrue(_source_is_known("deadbeefcafebabe" + "0" * 48, tokens))
        self.assertFalse(_source_is_known("feedfacecafebabe" + "0" * 48, tokens))

    def test_full_hash_match_blocks_exact_known_source(self) -> None:
        source_hash = "c" * 64
        self.assertTrue(_source_is_known(source_hash, {source_hash}))


if __name__ == "__main__":
    unittest.main()
