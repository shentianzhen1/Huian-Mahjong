# Ordered repository audit follow-up — 2026-10-13

Execution truth remains Issues #69/#45/#7. This note records completed work and
input prerequisites; it does not create a separate backlog or promotion gate.

## P0 completed: reject malformed promotion metrics

Code commit: `9f05355649e034906993bf04be06c49b761ffbf0`.

`promotion_gate.py` now checks metric domains before comparisons:
- policy/provenance flags must be actual booleans;
- counts must be nonnegative integers, excluding booleans and fractional values;
- rates must be finite numbers within [0, 1], excluding booleans;
- missing or malformed metrics produce failed checks with explicit reasons;
- rejection reports sanitize nonfinite/non-scalar values and serialize as
  strict JSON, including the CLI output-file path.

The numeric promotion thresholds are unchanged. This does not prove provenance
claims, calibrate a classifier, enable Executor, or improve tile recognition.

Validation: ten promotion-gate tests pass, including malformed-domain subtests
across every metric, malformed root/sections, integer unit rates, and CLI runs
for Infinity/NaN/string/nested nonfinite evidence. The final combined 33-test
run passed with four environment-dependent skips (29 passed, four skipped).
Tracked Python syntax checked 622 files with zero errors; diff whitespace checked.
GitHub CI is separate and must be read at the final branch HEAD before reporting
an all-green result.

## P1 next: fresh whole-hand candidate evaluation

Frozen development candidate definition:
- evaluator: `workspace/vision/tiles_runtime_v0_2/whole_hand_tight_fallback_probe.py`
  at base `782accca9dc07f887d79d77884d854a612bbacd5`;
- keep accepted primary identities; attempt tight detector crops only for UNKNOWN;
- fallback uses the existing identity/source-support rules and threshold 0.82;
- candidate support is the reconstructed packaged dataset plus the ten
  hash-verified Sep-26 crops described in the reproduction note;
- no blanket tight-crop replacement and no class-specific override.

Do not relabel the 43/43 development result as independent evidence.
Sep-19, Sep-26 and Oct-3 original matches have already been used for support or
development. Different files, uploads, hands and adjacent frames do not create
independent original matches.

Current availability check: the connected Drive folder "最近真实对局" contains
eight files, all named as segments of the Oct-3 recording and created on Oct-3.
No new original match was established from this listing. The label "10/9 batch"
in chat must not be interpreted as a new recording date or a new source group.
No candidate evaluation was run on these files in this follow-up.

Later inventory correction: the Drive root contains an actual separate `10-9`
folder with eight files labeled as Oct-9 recordings, plus a `10-13` folder with
two files labeled as Oct-12 recordings. The earlier listing covered only the
"最近真实对局" folder and was not a complete Drive inventory. Recording names
and separate folders still do not independently prove original-match grouping.
The Oct-12 files have not been opened or used for tuning in this follow-up.

Before one-pass evaluation, retain a private lock manifest containing:
1. query source SHA-256, reviewed original-match group and all derivative SHAs;
2. reviewed whole-hand truth/frame selection and truth-manifest SHA-256;
3. evaluator commit, exact candidate dataset file hashes and support groups;
4. recorded separation from every training/development original match;
5. the command, dependency versions, lock time and no-post-lock-tuning declaration.

The current probe reports development metrics; it does not establish independence
from a caller's group names alone. Review the actual dataset lineage, exclude all
same-original derivatives, and keep unknown lineage out of qualified evidence.
Source-exact exclusion alone is insufficient. If query data influence tuning,
move that match to development and use another untouched match for promotion.

Report exact-hand rate, wrong accepted hands, accepted/correct/wrong/rejected
tiles and own meld count/identity separately. A fresh candidate A/B run is not
by itself Issue #7's full Runtime promotion bundle.

## P1 downstream: actual detector melds and Windows capture

For own melds, measure automatic group count before exact identity on FLAT,
STACKED, add-kong and fragments. Preserve actual detector crops, count errors,
wrong identities and abstentions; manually corrected boxes are a separate
diagnostic and cannot establish automatic-path success.

For the Windows installed guarded live UI, retain build HEAD/RuleSnapshot,
source/epoch, frame truth, total capture-to-advice p50/p95, acquisition time,
changed-hand suppression, disconnect/worker-error recovery and new-hand reset.
Two distinct classified frames are required after changes/errors. A previous
hand cannot replace missing current evidence. Structural shanten needs complete
trusted hand/Gold/own meld count; unknown public identities keep remaining-copy
and danger disabled.

This Linux session cannot perform actual Windows mirrored-game capture.
Installer CI smoke is packaging/entrypoint evidence only. A real Windows session
and fresh reviewed query data remain prerequisites, not completed acceptance.

## P2 documentation and subsequent engineering

Current snapshot now distinguishes unchanged Runtime from the reproduced
development candidate. Earlier availability/sync notes link their successor
without deleting history. Active branch is PR #126; PR #117 is earlier work.

Review the large Draft PR by Rules, current-state/Hint, Vision experiments,
installer and evidence/documentation boundaries. Subsequent independently
reviewable changes should stay small; do not rewrite history or merge the PR
as cleanup. Windows runtime dependency version locking and general installer CI
scope are now implemented in the
[installer dependency contract](installer_reproducibility_20261013.md).
UI extraction remains later engineering work.

Frozen: Runtime identity 0.82; CurrentAgent V0.10; Hint internal/read-only;
UNKNOWN remains UNKNOWN; Executor OFF; PR #126 Draft/unmerged.
