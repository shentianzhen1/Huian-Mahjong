# Runtime Vision V0.2 — Independent Batch Intake

This is the required local intake flow for a fresh formal promotion attempt.

## Why this exists

A source-disjoint batch stops being a blind promotion batch once detector/classifier
results are inspected and then used to tune thresholds, templates, geometry, or
selection logic.

The intake step therefore happens **before** any model evaluation.

## 1. Prepare a fresh local folder

Put only intended new independent recordings under one local directory.

Do not:
- copy old Phase 5/5B/5C development recordings into the folder;
- pre-label the videos;
- add their frames to tile templates;
- run detector-driven review first.

## 2. Lock the batch

Example:

```powershell
python -m workspace.vision.tiles_runtime_v0_2.independent_batch_lock ^
  --root D:\huian_new_blind_batch
```

Default output:

`data/vision_independent_batches/<anonymous_batch_id>/`

The locker:
- hashes all video candidates;
- rejects tracked development-source hashes / anonymous source prefixes;
- requires at least 8 source-disjoint sessions;
- ignores recordings shorter than 120 frames;
- deterministically selects source sessions by content hash;
- freezes 20% / 50% / 80% frame positions;
- writes no local filename or path into persisted artifacts;
- never calls detector/classifier code.

## 3. Locked artifacts

### batch_lock.json

Anonymous source hashes, dimensions, frame counts and frozen frame selections.

Once created, the locker refuses to overwrite the same batch artifacts.

### geometry_truth.blank.jsonl

Metadata-only manual-review skeleton.

Important:
- `manual_truth_required=true`;
- `frame_state=null`;
- `components=null`;
- `approved=false`.

These nulls are deliberate. Detector output must not populate manual truth.

### promotion_bundle.blank.json

Contains frozen provenance:
- `independent_batch=true`;
- `holdout_locked_before_evaluation=true`;
- `tuning_after_lock=false`;
- source-session count;
- `safe_for_executor=false`.

Every performance metric starts as `null`.

## 4. Manual truth

A human reviewer fills truth from the raw source frames without model suggestions.

Only after manual truth is frozen should Runtime V0.2 detector/classifier/draw/
PublicState/Gold evaluation run.

## 5. Promotion gate

After all independent metrics are measured, fill the locked promotion bundle and run:

```powershell
python -m workspace.vision.tiles_runtime_v0_2.promotion_gate ^
  --bundle <promotion_bundle.json> ^
  --output <promotion_gate_report.json>
```

Any missing metric fails closed.

## 6. If a gate fails

The batch becomes revealed development evidence.

It may be used for error analysis, but after tuning/fixing on it, the next formal
promotion attempt requires a **new untouched source-disjoint batch**.

Do not relock the same videos and call them independent again.

## Scope boundary

Passing the promotion gate may promote Runtime Vision V0.2 only to the formal
**read-only observation baseline**.

It never sets `executor_ready=true`; Executor still requires a separate safety gate.
