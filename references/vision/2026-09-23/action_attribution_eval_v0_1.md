# #69 — Continuous-source public action / actor / turn evaluation V0.1

This is an **evidence intake and development evaluation tool**, not a claim of
real-video accuracy, a new Mahjong rule, or a Vision/Executor promotion gate.

The existing archived eight-hand replay has source video SHA256, sparse
timepoints, and settlement truth, but **the raw videos are not committed**.
Sparse frames and repeated copies of one reviewed JPG cannot establish
continuous-frame false-track rates or who acted between samples.

## Inputs: keep manual truth and machine predictions separate

Copy the two **blank** templates in this directory to local, ignored working
files. The blank truth template intentionally has `truth_frozen=false`,
`source_session=null`, `source_sha256=null`, no intervals and no events: running
the evaluator on it must fail. Do not fill it with detector output.

1. Select one accessible, continuous recording and verify the SHA256 of its
   **actual binary**. Use an anonymized `source_session` with that SHA256.
2. A reviewer watches the *raw video without prediction overlays*. For each
   contiguous interval fully reviewed, record its tracking `stream_epoch`,
   start/end source-relative timestamps, first/last source frame and a
   source/frame evidence reference. Only label intervals where the reviewer
   can account for **all public action events**, including sections with no
   actions, so predictions in quiet periods can be false positives.
3. Record approved human `events` (`DISCARD`, `CHI`, `PENG`, `MING_GANG`,
   `ADD_KONG`, `HU`), with video-relative timestamp, actual source frame,
   visible `actor` (`player` or `opponent`), optional known tile and optional
   independently **visible** `turn_actor`. If the turn cannot be seen, keep
   `turn_actor=null`; do not copy it from the inferred action actor.
4. Freeze truth **before** looking at machine results. Only then set
   `truth_frozen=true` in the truth file. Record whether this is
   `development_continuous_video` or a separately locked
   `source_disjoint_continuous_video` batch; this field is a human declaration,
   not proof of holdout provenance.
5. Export the separate predictions file from reconstructed public actions,
   preserving each action's `source_session`, `stream_epoch`, timestamp, kind,
   actor, optional independently observed turn, confidence, evidence grade and
   frame references. Set the predictions-file `source_sha256` from the verified
   capture manifest. `prediction_from_action()` converts a
   `ReconstructedAction` without inventing a turn or source identifier.

Example **shape only** for one reviewed interval:

```json
{
  "schema_version": "public_action_attribution_eval_v0_1",
  "source_session": "anonymous-session-id",
  "source_sha256": "<verified lowercase 64-hex recording hash>",
  "review_kind": "development_continuous_video",
  "truth_frozen": true,
  "reviewed_intervals": [
    {
      "stream_epoch": 0,
      "start_seconds": 10.0,
      "end_seconds": 20.0,
      "first_frame": 300,
      "last_frame": 600,
      "evidence_refs": ["anonymous-session-id:reviewed:frames:300-600"]
    }
  ],
  "events": [
    {
      "timestamp_seconds": 12.4,
      "stream_epoch": 0,
      "frame": 372,
      "kind": "DISCARD",
      "actor": "opponent",
      "turn_actor": null,
      "tile": null,
      "evidence_refs": ["anonymous-session-id:frame:372"]
    }
  ]
}
```

The example values are **illustrative**, not a claim about the archived footage.
The real JSON templates are blank and deliberately unscorable. Video sources,
their timestamps and screenshots must never be fabricated to make the gate pass.

## Run

```bash
python -m workspace.vision.action_attribution_eval \
  --truth path/to/frozen_manual_truth.json \
  --predictions path/to/separate_machine_predictions.json \
  --output path/to/action_attribution_report.json \
  --tolerance-seconds 0.35
```

The 0.35-second default is a *review alignment parameter*, not a Mahjong rule
or a validated live-capture tolerance; report it with every evaluation and
inspect video for ambiguous timing.

## Reporting and fail-closed semantics

- Predictions from another recording SHA256 **cannot** be evaluated against
  this truth even if the two recordings reuse the same display/session alias.
  A prediction without explicit matching session/epoch, or outside all
  reviewed intervals, is reported as out of scope, never silently matched.
- Alignment is one-to-one within one `stream_epoch` and time tolerance. Actor
  is **not** used to select the pair: a same-time wrong actor is explicitly
  `wrong_actor`, not hidden by matching only successful actors.
- `UNKNOWN_ACTION`, `EVIDENCE_CONFLICT`, unknown actor/grade, missing confidence,
  zero confidence or missing frame references **abstain**. An abstention is not
  counted as a correct action; the human truth event remains missed.
- Wrong kind, actor or known tile counts as one event false positive **and**
  one event false negative. Extra machine events in a reviewed no-event period
  count as false positives. Missing machine events count as false negatives.
  If there is no denominator, precision or accuracy is `null`, not 100%.
- Turn is scored **separately** on aligned human events with independent
  turn labels. Unknown machine turns lower *turn coverage* but do not enter
  *turn accuracy when known*. Reporting accuracy without coverage is misleading.
- The report contains per-match frame evidence refs, unmatched truth indexes,
  extra prediction indexes, abstention indexes and source/epoch rejection
  indexes. One report is one recording hash; run separately for each source.
- An `APPEARED` geometric candidate is **not a DISCARD**. This evaluator
  measures *action-event* errors and actor/turn attribution, not track
  APPEARED precision/recall. That needs separate reviewed presence/negative
  frame labels and source-disjoint evaluation before formal Vision promotion.

All regression tests here use **synthetic contract examples** and emit
`review_kind=synthetic_contract`. Never report their perfect scores as
real-video performance. Output always has
`formal_promotion_evidence=false` and `safe_for_executor=false`.

## Follow-up for #69

After a new accessible continuous recording is reviewed, export its actual
candidate tracker APPEARED/DISAPPEARED stream, public river/meld snapshots,
HAND_DELTA and assembler actions. Populate and freeze human truth first; then
run this evaluator for actor/turn and event-level false positives/misses.
Preserve UNKNOWN where public tile identities and turns are unverified.
Formal Vision promotion under #7 uses a **different untouched holdout batch**.
