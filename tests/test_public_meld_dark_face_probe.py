import pytest
pytest.importorskip("cv2")
pytest.importorskip("numpy")
from PIL import Image
from workspace.vision.public_meld_dark_face_probe import dark_face_front_band_bbox


def _image():
    # Two-tone synthetic face with a darker lower side band.
    import numpy as np
    a = np.full((96, 80, 3), 105, dtype=np.uint8)
    a[4:76, :] = 150
    a[76:, :] = 92
    return Image.fromarray(a)


def test_fallback_rejects_every_other_primary_reason():
    for reason in ("development_front_band_candidate", "no_lower_side_band",
                   "lower_band_not_darker", "weak_brightness_separation",
                   "normalization_abstained"):
        box, audit = dark_face_front_band_bbox(_image(), {"reason": reason})
        assert box is None
        assert audit["reason"] == "fallback_not_permitted"


def test_fallback_remains_development_only_and_fail_closed():
    box, audit = dark_face_front_band_bbox(
        _image(), {"reason": "ambiguous_or_absent_front_component"})
    assert audit["development_only"] is True
    assert audit["runtime_integration"] is False
    assert audit["tile_identity"] == "UNKNOWN"
    assert audit["safe_for_runtime"] is False
    assert audit["safe_for_hint"] is False
    assert audit["safe_for_executor"] is False


def test_uniform_crop_cannot_be_forced_through_fallback():
    image = Image.new("RGB", (80, 96), (100, 100, 100))
    box, audit = dark_face_front_band_bbox(
        image, {"reason": "ambiguous_or_absent_front_component"})
    assert box is None
    assert audit["reason"] in {
        "no_two_brightness_populations", "weak_brightness_separation",
        "ambiguous_or_absent_front_component", "no_lower_side_band",
        "lower_band_not_darker",
    }
