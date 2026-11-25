"""Paired ledgers preserve abstentions/coverage losses in every denominator."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def compare(before: dict, after: dict) -> dict:
    old = {r["query_id"]: r for r in before["rows"]}
    new = {r["query_id"]: r for r in after["rows"]}
    if set(old) != set(new):
        raise ValueError("paired query set changed")
    summary = {}
    for n in ("1", "2"):
        summary[n] = {}
        for packet in sorted({r["set"] for r in old.values()}):
            ids = [q for q, r in old.items() if r["set"] == packet]
            summary[n][packet] = dict(query_faces=len(ids),
                correct_family_before=sum(old[q]["modes"][n]["consensus_correct"] is True for q in ids),
                correct_family_after=sum(new[q]["modes"][n]["consensus_correct"] is True for q in ids),
                family_regressions=[q for q in ids if old[q]["modes"][n]["consensus_correct"] is True and new[q]["modes"][n]["consensus_correct"] is not True],
                true_identity_support_losses=[q for q in ids if old[q]["modes"][n]["expected_identity_scorable"] and not new[q]["modes"][n]["expected_identity_scorable"]],
                digit_correct_before=sum(old[q]["modes"][n]["routed_identity_correct"] is True for q in ids),
                digit_correct_after=sum(new[q]["modes"][n]["routed_identity_correct"] is True for q in ids),
                digit_regressions=[q for q in ids if old[q]["modes"][n]["routed_identity_correct"] is True and new[q]["modes"][n]["routed_identity_correct"] is not True],
                false_wan_routes_before=[q for q in ids if old[q]["modes"][n]["false_wan_route"]],
                false_wan_routes_after=[q for q in ids if new[q]["modes"][n]["false_wan_route"]])
    rows = []
    def thin(m):
        return dict(whole_top1=m["family_ranking"]["top1_tile"],
                    lower_top1=m["lower_binary_ranking"]["top1_tile"],
                    family_consensus=m["family_consensus"], consensus_correct=m["consensus_correct"],
                    expected_identity_scorable=m["expected_identity_scorable"],
                    false_wan_route=m["false_wan_route"],
                    digit_top1=m["digit_ranking"]["top1_tile"] if m["digit_ranking"] else None,
                    digit_true_class_scorable=m["routed_expected_identity_scorable"],
                    digit_correct=m["routed_identity_correct"],
                    qualified_identity=m["qualified_identity"])
    for q, a in old.items():
        b = new[q]
        for key in ("expected", "sha256", "crop_sha256", "set"):
            if a.get(key) != b.get(key):
                raise ValueError("paired source/label pin changed")
        row = dict(query_id=q, packet=a["set"], expected=a["expected"], source_sha256=a["sha256"],
                   crop_sha256=a.get("crop_sha256"), modes={n: dict(before=thin(a["modes"][n]), after=thin(b["modes"][n])) for n in ("1", "2")})
        if a["set"] == "new_native_reverse_queries" and a["expected"] == "M9":
            row["reverse_M9_full_ranks"] = {n: dict(before=a["modes"][n], after=b["modes"][n]) for n in ("1", "2")}
        rows.append(row)
    return dict(summary=summary, paired_query_count=len(rows), rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "front", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    for name in ("reverse-baseline", "reverse-front"):
        parser.add_argument("--"+name, type=Path)
    parser.add_argument("--overlap-only", action="store_true")
    parser.add_argument("--bracketed-peer", action="store_true")
    parser.add_argument("--body-baseline", type=Path)
    args = parser.parse_args()
    if args.bracketed_peer:
        if args.overlap_only or args.body_baseline is None:
            parser.error("bracketed-peer requires body-baseline and cannot combine with overlap-only")
        before = json.loads(args.baseline.read_text())
        after = json.loads(args.front.read_text())
        body = json.loads(args.body_baseline.read_text())
        if (before.get("bracketed_peer_band_enabled", False)
                or not after.get("bracketed_peer_band_enabled", False)
                or not before["merge_front_overlaps_enabled"]
                or not after["merge_front_overlaps_enabled"]
                or not before["symmetric_front_band_enabled"]
                or not after["symmetric_front_band_enabled"]
                or body.get("symmetric_front_band_enabled", False)
                or any(p.get("reverse_old_m9_references_enabled", False) for p in (before, after, body))):
            raise ValueError("expected body/overlap/bracketed modes without reverse additions")
        report = dict(schema_version="bracketed_front_identity_paired_comparison_dev_v0_1",
            input_sha256={name: hashlib.sha256(path.read_bytes()).hexdigest()
                for name, path in (("body", args.body_baseline), ("overlap", args.baseline), ("bracketed", args.front))},
            against_overlap=compare(before, after), against_body_baseline=compare(body, after),
            all_queries_kept_in_denominators=True, whole_lower_views_independent_evidence=False,
            decision="retain bracketed geometry diagnostic; reject global feature replacement due to remaining coverage/control losses and two-source reverse family abstentions",
            runtime_identity_threshold=0.82, runtime_integration=False, formal_promotion_evidence=False,
            safe_for_runtime=False, safe_for_hint=False, safe_for_executor=False)
        args.output.write_text(json.dumps(report, separators=(",", ":"))+"\n")
        print(json.dumps(report["against_overlap"]["summary"]))
        return
    if args.overlap_only:
        before = json.loads(args.baseline.read_text())
        after = json.loads(args.front.read_text())
        if (not before["symmetric_front_band_enabled"] or not after["symmetric_front_band_enabled"]
                or before.get("merge_front_overlaps_enabled", False)
                or not after.get("merge_front_overlaps_enabled", False)
                or before["reverse_old_m9_references_enabled"] or after["reverse_old_m9_references_enabled"]):
            raise ValueError("overlap comparison requires strict versus overlap mode without reverse additions")
        report = dict(schema_version="front_band_overlap_paired_comparison_dev_v0_1",
            input_sha256={name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for name, path in (("strict", args.baseline), ("overlap", args.front))},
            paired=compare(before, after), all_queries_kept_in_denominators=True,
            whole_lower_views_independent_evidence=False,
            decision="retain optional overlapping-component diagnostic; reject global front-band replacement",
            runtime_identity_threshold=0.82, runtime_integration=False, formal_promotion_evidence=False,
            safe_for_runtime=False, safe_for_hint=False, safe_for_executor=False)
        args.output.write_text(json.dumps(report, separators=(",", ":"))+"\n")
        print(json.dumps(report["paired"]["summary"]))
        return
    if args.reverse_baseline is None or args.reverse_front is None:
        parser.error("reverse-baseline and reverse-front are required unless overlap-only is selected")
    paths = dict(baseline=args.baseline, front=args.front, reverse_baseline=args.reverse_baseline, reverse_front=args.reverse_front)
    payloads = {name: json.loads(path.read_text()) for name, path in paths.items()}
    reverse_baseline, reverse_front = payloads["reverse_baseline"], payloads["reverse_front"]
    if reverse_baseline["reverse_reference_feature_rows"] != reverse_front["reverse_reference_feature_rows"]:
        raise ValueError("reverse reference selection/availability changed")
    report = dict(schema_version="front_band_identity_paired_comparison_dev_v0_1",
        input_sha256={name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()},
        without_old_M9_references=compare(payloads["baseline"], payloads["front"]),
        with_same_three_old_M9_references=compare(reverse_baseline, reverse_front),
        reverse_reference_pins=reverse_front["reverse_reference_feature_rows"],
        all_queries_kept_in_denominators=True, whole_lower_views_independent_evidence=False,
        decision="reject global feature replacement; limited M9 reverse gain is diagnostic only",
        private_loader_verification_contract_changed=False,
        runtime_identity_threshold=0.82, runtime_integration=False, formal_promotion_evidence=False,
        safe_for_runtime=False, safe_for_hint=False, safe_for_executor=False)
    args.output.write_text(json.dumps(report, separators=(",", ":"))+"\n")
    print(json.dumps({"without_old_refs": report["without_old_M9_references"]["summary"]["1"],
                      "with_same_old_refs": report["with_same_three_old_M9_references"]["summary"]["1"]}))


if __name__ == "__main__":
    main()
