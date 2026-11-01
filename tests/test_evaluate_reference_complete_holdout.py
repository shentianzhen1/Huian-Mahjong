from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workspace.vision.evaluate_reference_complete_holdout import (
    assert_frozen_environment,
    assert_frozen_inputs,
)


REPO = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO / "references/vision/2026-10-03/holdout3_p456_reference_complete_spec_v0_1.json"


class ReferenceCompleteHoldoutRunnerTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    def test_frozen_dependency_versions_are_required(self):
        assert_frozen_environment(
            cv2_version="5.0.0",
            numpy_version="2.5.3",
            spec=self.spec,
        )
        with self.assertRaisesRegex(RuntimeError, "OpenCV 5.0.0"):
            assert_frozen_environment(
                cv2_version="4.13.0",
                numpy_version="2.5.3",
                spec=self.spec,
            )
        with self.assertRaisesRegex(RuntimeError, "NumPy 2.5.3"):
            assert_frozen_environment(
                cv2_version="5.0.0",
                numpy_version="2.3.5",
                spec=self.spec,
            )

    def test_input_hash_mismatch_fails_before_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "3.mp4"
            private = root / "templates.zip"
            bottom = root / "bottom.mp4"
            video.write_bytes(b"not the pinned holdout")
            private.write_bytes(b"not the pinned templates")
            bottom.write_bytes(b"not the pinned reference")
            with self.assertRaisesRegex(RuntimeError, "holdout video SHA mismatch"):
                assert_frozen_inputs(
                    video_path=video,
                    private_template_zip=private,
                    bottom_reference_video=bottom,
                    spec=self.spec,
                )


if __name__ == "__main__":
    unittest.main()
