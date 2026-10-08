"""Run the frozen reference-completeness scorer on the pinned 3.mp4 holdout.

Private video/template pixels stay outside the repository.  This runner fails
closed before scoring when the exact frozen dependency or input contract is
not present, so a non-reproducible local run cannot become the holdout's first
reported result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_PRIVATE_ZIP_SHA256 = (
    "e1dcede193c7e7d3f0c241ee9110bb0c8decd9048be372e5e1e25dbf0623d83c"
)
EXPECTED_BOTTOM_REFERENCE_SHA256 = (
    "4ffc9187a08df3d11df34a8a0c087b31172cf39104920cc0e9ebd5f2e72780c4"
)


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assert_frozen_environment(*, cv2_version: str, numpy_version: str, spec: dict) -> None:
    contract = spec["scorer_contract"]
    if cv2_version != contract["opencv_cv2"]:
        raise RuntimeError(
            f"holdout requires OpenCV {contract['opencv_cv2']}; got {cv2_version}"
        )
    if numpy_version != contract["numpy"]:
        raise RuntimeError(
            f"holdout requires NumPy {contract['numpy']}; got {numpy_version}"
        )


def assert_frozen_inputs(
    *,
    video_path: str | Path,
    private_template_zip: str | Path,
    bottom_reference_video: str | Path,
    spec: dict,
) -> None:
    source = spec["sources"][0]
    checks = (
        ("holdout video", _sha256(video_path), source["source_sha256"]),
        ("private template ZIP", _sha256(private_template_zip), EXPECTED_PRIVATE_ZIP_SHA256),
        ("bottom reference video", _sha256(bottom_reference_video), EXPECTED_BOTTOM_REFERENCE_SHA256),
    )
    for name, actual, expected in checks:
        if actual != expected:
            raise RuntimeError(f"{name} SHA mismatch")


def evaluate_pinned_holdout(
    *,
    video_path: str | Path,
    private_template_zip: str | Path,
    bottom_reference_video: str | Path,
    spec_path: str | Path = (
        "references/vision/2026-10-03/"
        "holdout3_p456_reference_complete_spec_v0_1.json"
    ),
) -> dict:
    import cv2
    import numpy as np

    spec_path = Path(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert_frozen_environment(
        cv2_version=cv2.__version__,
        numpy_version=np.__version__,
        spec=spec,
    )
    assert_frozen_inputs(
        video_path=video_path,
        private_template_zip=private_template_zip,
        bottom_reference_video=bottom_reference_video,
        spec=spec,
    )

    from workspace.vision.evaluate_sift_detector_body_boundary_probe import evaluate

    result = evaluate(
        video_path,
        private_template_zip,
        spec_file=str(spec_path),
        source_index=0,
        group_index=0,
        reference_geometry=True,
        bottom_reference_video=bottom_reference_video,
        bottom_reference_rectified=True,
        score_policy="spatial_window_affine_reference_complete",
    )
    expected_modes = set(spec["scorer_contract"]["required_modes"])
    actual_modes = set(result["summary"])
    if actual_modes != expected_modes:
        raise RuntimeError("holdout crop-mode set changed")
    return {
        "schema_version": "holdout3_p456_reference_complete_result_v0_1",
        "first_result_contract": True,
        "candidate_frozen_formula_commit": spec["scorer_contract"]["frozen_formula_commit"],
        "source_sha256": spec["sources"][0]["source_sha256"],
        "reviewed_candidate_tiles": spec["sources"][0]["groups"][0]["reviewed_candidate_tiles"],
        "summary": result["summary"],
        "rows": result["rows"],
        "dependency_versions": result["dependency_versions"],
        "development_only": True,
        "source_disjoint_holdout": True,
        "parameter_retuned_after_holdout": False,
        "formal_promotion_evidence": False,
        "runtime_integration": False,
        "safe_for_runtime": False,
        "safe_for_hint": False,
        "safe_for_executor": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--private-template-zip", required=True)
    parser.add_argument("--bottom-reference-video", required=True)
    parser.add_argument("--spec", default=(
        "references/vision/2026-10-03/"
        "holdout3_p456_reference_complete_spec_v0_1.json"
    ))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = evaluate_pinned_holdout(
        video_path=args.video,
        private_template_zip=args.private_template_zip,
        bottom_reference_video=args.bottom_reference_video,
        spec_path=args.spec,
    )
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
