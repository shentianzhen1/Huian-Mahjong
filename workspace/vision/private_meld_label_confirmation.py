"""Human confirmation of a PRIVATE public-meld review packet (Issue #69).

The user-approved labels live in a separate PRIVATE sidecar: never overwrite
the pending candidate packet or commit videos/crops/private source SHA values
to GitHub. A prior assistant's visual proposal is only an approved development
label after the user has explicitly confirmed the *exact* review sheet.
Neither confirmation nor same-match testing certifies runtime identities.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZipFile, ZIP_DEFLATED

from workspace.vision.private_meld_review_audit import audit_private_meld_packet
from workspace.vision.tiles_v0_1.taxonomy import TILE_CLASSES

_SCHEMA = "private_existing_evidence_review_v0_1"
_APPROVAL_SCHEMA = "private_meld_review_user_confirmation_v0_1"
_REQUIRED = {
    "pending_faces/manifest.json",
    "private_pixel_integrity_and_pending_proposals.json",
    "private_review_visual_proposals.jpg",
    "private_source_registry_for_local_reaudit.json",
}
_OPTIONAL = {
    "readme_chinese.md", "private_temporal_geometry_stability.json"
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def confirm_existing_private_faces(
    *,
    archive_path: str | Path,
    user_declaration_path: str | Path,
    videos_dir: str | Path,
    private_registry_path: str | Path,
    output_path: str | Path,
    expected_groups: int = 12,
    expected_faces: int = 36,
) -> dict[str, Any]:
    """Re-audit original private pixels before issuing development-only labels.

    The declaration must bind the exact ZIP and the JPEG the user saw.
    The original ZIP retains UNKNOWN/pending states; approvals are separate.
    Source-video SHA and exact source crop pixels are checked by the already
    tested private_meld_review_audit, via a strict temporary flat ZIP adapter.
    """
    packet = Path(archive_path)
    declaration = json.loads(Path(user_declaration_path).read_text("utf-8"))
    target = Path(output_path).resolve()
    checkout = Path(__file__).resolve().parents[2]
    if target == checkout or checkout in target.parents:
        raise ValueError("private approved labels cannot be written inside checkout")
    if target.exists():
        raise ValueError("do not overwrite an earlier approval")
    if (not isinstance(declaration, dict)
            or set(declaration) != {
                "schema_version", "source_packet_sha256", "review_sheet_sha256",
                "confirmed_group_ids", "user_explicitly_confirmed_all"
            } or declaration["schema_version"] != _APPROVAL_SCHEMA
            or declaration["user_explicitly_confirmed_all"] is not True):
        raise ValueError("explicit scoped user confirmation required")
    if sha256(packet.read_bytes()) != declaration["source_packet_sha256"]:
        raise ValueError("review packet SHA mismatch")

    with ZipFile(packet) as source:
        names = source.namelist()
        if (len(names) != len(set(names))
                or not _REQUIRED.issubset(names)
                or len(names) > expected_faces + len(_REQUIRED) + len(_OPTIONAL)
                or any(name != "pending_faces/manifest.json"
                       and name not in _REQUIRED | _OPTIONAL
                       and not (
                           name.startswith("pending_faces/")
                           and len(Path(name).parts) == 2
                           and Path(name).name.endswith(".png")
                           and Path(name).name.replace("_", "").replace(".", "").isalnum()
                       ) for name in names)
                or any(zinfo.file_size > 4 * 1024 * 1024 for zinfo in source.infolist())):
            raise ValueError("unsafe or incomplete private review archive")
        sheet = source.read("private_review_visual_proposals.jpg")
        if sha256(sheet) != declaration["review_sheet_sha256"]:
            raise ValueError("confirmed review sheet SHA mismatch")
        manifest = json.loads(source.read("pending_faces/manifest.json"))
        proposals = json.loads(source.read(
            "private_pixel_integrity_and_pending_proposals.json"
        ))
        registry = json.loads(Path(private_registry_path).read_text("utf-8"))
        packet_registry = json.loads(source.read(
            "private_source_registry_for_local_reaudit.json"
        ))
        if registry != packet_registry:
            raise ValueError("external source registry differs from reviewed packet")
        if (manifest.get("schema_version") != _SCHEMA
                or manifest.get("development_only") is not True
                or manifest.get("requires_human_review") is not True
                or manifest.get("source_disjoint_holdout") is not False
                or manifest.get("identity_accuracy") is not None
                or manifest.get("extracted_group_count") != expected_groups
                or manifest.get("extracted_face_slots") != expected_faces
                or proposals.get("user_confirmed_labels") != 0
                or proposals.get("pixel_verified_faces") != expected_faces
                or proposals.get("pixel_verified_groups") != expected_groups
                or not isinstance(manifest.get("groups"), list)
                or len(manifest["groups"]) != expected_groups
                or not isinstance(proposals.get("groups_review"), list)
                or len(proposals["groups_review"]) != expected_groups
                or declaration["confirmed_group_ids"] != [
                    f"G{i:02d}" for i in range(1, expected_groups + 1)
                ]):
            raise ValueError("incomplete development-only all-group confirmation")

        normalized = {"schema_version": _SCHEMA,
                      "development_only": True,
                      "source_disjoint_holdout": False,
                      "requires_human_review": True,
                      "identity_accuracy": None,
                      "extracted_group_count": expected_groups,
                      "extracted_face_slots": expected_faces,
                      "groups": []}
        approved: list[dict[str, Any]] = []
        copied: dict[str, bytes] = {}
        for i, (group, suggestion) in enumerate(
                zip(manifest["groups"], proposals["groups_review"]), 1):
            if (suggestion.get("group_no") != i
                    or suggestion.get("clip") != group.get("clip")
                    or suggestion.get("match_group") != group.get("match_group")
                    or suggestion.get("all_three_crops_match_source_pixels") is not True
                    or group.get("human_approved") is not False
                    or group.get("formal_promotion_evidence") is not False
                    or group.get("tile_identity_policy") != "UNKNOWN"
                    or not isinstance(group.get("faces"), list)
                    or len(group["faces"]) != 3
                    or not isinstance(suggestion.get("faces"), list)
                    or len(suggestion["faces"]) != 3):
                raise ValueError("missing or unreviewed group provenance")
            normalized["groups"].append(group)
            for n, (face, proposed) in enumerate(
                    zip(group["faces"], suggestion["faces"])):
                name = face.get("relative_crop_file")
                if (not isinstance(name, str) or "/" in name
                        or f"pending_faces/{name}" not in names
                        or face.get("index") != proposed.get("face_index") != n
                        or name != proposed.get("crop_file")
                        or face.get("tile_id") != "UNKNOWN"
                        or face.get("review_status") != "pending_human_adjudication"):
                    raise ValueError("face proposal does not match original pending crop")
                tile = proposed.get("visual_candidate")
                if tile not in TILE_CLASSES or tile.startswith("F"):
                    raise ValueError("invalid proposed public tile identity")
                png = source.read("pending_faces/" + name)
                if (sha256(png) != proposed.get("crop_sha256")
                        or name in copied):
                    raise ValueError("altered or duplicate face crop")
                copied[name] = png
                approved.append({
                    "group_id": f"G{i:02d}", "face_index": n,
                    "clip": group["clip"], "match_group": group["match_group"],
                    "relative_crop_file": name, "crop_sha256": sha256(png),
                    "approved_tile_id": tile,
                    "review_status": "user_confirmed_assistant_proposal",
                    "public_action_kind": "UNKNOWN", "actor": "UNKNOWN",
                    "formal_promotion_evidence": False,
                    "safe_for_runtime": False, "safe_for_executor": False,
                })
        if len(copied) != expected_faces:
            raise ValueError("incomplete public face count")
        if set(names) != _REQUIRED | (set(names) & _OPTIONAL) | {
                "pending_faces/" + key for key in copied}:
            raise ValueError("unknown archive member")

        with TemporaryDirectory(prefix="private_review_audit_") as tmp:
            # Flatten only known/validated source file paths for PR #104's
            # exact-video-frame pixel audit. No approval can precede it.
            flat = Path(tmp) / "flat_pending.zip"
            with ZipFile(flat, "w", ZIP_DEFLATED) as z:
                z.writestr("manifest.json", json.dumps(normalized))
                for name, blob in copied.items():
                    z.writestr(name, blob)
            evidence = audit_private_meld_packet(
                flat, videos_dir, private_registry_path
            )
        if (evidence.get("source_verified_groups") != expected_groups
                or evidence.get("source_verified_faces") != expected_faces
                or evidence.get("original_matches") < 1
                or evidence.get("formal_promotion_evidence") is not False):
            raise ValueError("original-video pixel audit did not pass")
        result = {
            "schema_version": "private_meld_confirmed_labels_development_v0_1",
            "source_packet_sha256": declaration["source_packet_sha256"],
            "review_sheet_sha256": declaration["review_sheet_sha256"],
            "confirmation_scope": declaration["confirmed_group_ids"],
            "human_confirmed_faces": len(approved),
            "human_confirmed_groups": expected_groups,
            "original_match_groups": evidence["original_matches"],
            "pixel_verification": "all_approved_faces_match_locked_source_video",
            "review_provenance": "user_approved_prior_assistant_visual_proposals",
            "independent_blind_holdout": False,
            "source_disjoint_holdout": False,
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
            "labels": approved,
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8"
        )
        return {
            "human_confirmed_faces": len(approved),
            "human_confirmed_groups": expected_groups,
            "original_match_groups": evidence["original_matches"],
            "safe_for_runtime": False,
            "formal_promotion_evidence": False,
        }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--user-declaration", required=True)
    parser.add_argument("--videos", required=True)
    parser.add_argument("--private-registry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = confirm_existing_private_faces(
        archive_path=args.archive,
        user_declaration_path=args.user_declaration,
        videos_dir=args.videos,
        private_registry_path=args.private_registry,
        output_path=args.output,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
