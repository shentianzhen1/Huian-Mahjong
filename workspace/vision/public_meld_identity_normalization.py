"""Development-only QUERY-side identity normalization for exposed meld faces.

Geometry normalization answers "where is the meld and where are its faces?".
This layer is deliberately narrower: after a Runtime/development query face has
already been split, it can test whether excess outer border causes an identity
crop-domain mismatch.

The current 0.12 inset was selected after inspecting the same two first-hand
P6/S4 development queries. A separate private 36-face check showed that applying
this inset to already-tight reviewed crops does NOT improve identity retrieval.
Therefore this transform is query-side only: it must not preprocess the
reviewed template bank and is NOT a Runtime threshold or promotion result.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEVELOPMENT_IDENTITY_INSET_RATIO = 0.12


@dataclass(frozen=True)
class PublicMeldIdentityNormalization:
    image: Any
    inset_ratio: float
    input_size: tuple[int, int]
    output_size: tuple[int, int]
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": "public_meld_identity_normalization_v0_1",
            "inset_ratio": self.inset_ratio,
            "input_size": list(self.input_size),
            "output_size": list(self.output_size),
            "issues": list(self.issues),
            "development_only": True,
            "selected_on_reviewed_queries": True,
            "intended_scope": "query_side_split_face_only",
            "template_bank_preprocessing_allowed": False,
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_hint": False,
            "safe_for_executor": False,
        }


def normalize_public_meld_identity_query_face(
    image: Any,
    *,
    inset_ratio: float = DEVELOPMENT_IDENTITY_INSET_RATIO,
) -> PublicMeldIdentityNormalization:
    """Center-inset one already-split QUERY face and restore its dimensions.

    This deterministic transform never inspects tile identity or class labels.
    It is intentionally not a template-bank preprocessing function.
    """
    from PIL import Image

    if isinstance(inset_ratio, bool) or not isinstance(inset_ratio, (int, float)):
        raise ValueError("inset_ratio must be numeric")
    inset_ratio = float(inset_ratio)
    if not 0 <= inset_ratio < 0.5:
        raise ValueError("inset_ratio must be in [0, 0.5)")

    rgb = image.convert("RGB")
    width, height = rgb.size
    if width < 8 or height < 12:
        raise ValueError("public meld identity face is too small")

    if inset_ratio == 0:
        return PublicMeldIdentityNormalization(
            image=rgb.copy(),
            inset_ratio=0.0,
            input_size=(width, height),
            output_size=(width, height),
            issues=("query_identity_face_inset_disabled",),
        )

    dx = max(1, int(round(width * inset_ratio)))
    dy = max(1, int(round(height * inset_ratio)))
    if dx * 2 >= width or dy * 2 >= height:
        raise ValueError("identity face inset removes the full image")

    normalized = rgb.crop(
        (dx, dy, width - dx, height - dy)
    ).resize((width, height), Image.Resampling.LANCZOS)
    return PublicMeldIdentityNormalization(
        image=normalized,
        inset_ratio=inset_ratio,
        input_size=(width, height),
        output_size=(width, height),
        issues=("development_query_identity_face_center_inset",),
    )
