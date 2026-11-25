# Whole-project audit and bounded fixes — 2026-10-18

Execution truth: Issues #69/#45/#7 and rule-migration Issues. Audited remote base:
`7f3653804e4e68b484d2c0cda5f645d0d2e6d6dd`, Draft PR #126, five successful
workflows. This report is an engineering audit, not a new backlog, independent
Vision evaluation, security certification or release authorization.

## Conclusion and scope

Keep the existing layered architecture and V0.10 strategy. The immediate product
gap is still trustworthy complete current input and real capture validation,
not a new Agent, automatic clicks or exhaustive transcription of eight hands.
Do not promote the revealed private candidate based on its two perfect windows.

| Area reviewed | Evidence / result | Boundary retained |
| --- | --- | --- |
| Rules / Environment | Current rule truth, snapshot revisions and regression suite; ordinary settlement/Kong scoring no longer an unknown gap | No rule or control-flow changes |
| AI / Simulator | V0.10 baseline, ordinary match fixtures and import-boundary regressions | No new strategy or EV claims |
| Vision / public adapter / Hint | Score trust, Gold/hand conversion, structural capability gates, live state/freshness regression coverage | UNKNOWN, source support and 0.82 preserved |
| Replay / evidence | Exact frame selection, early EOF handling, user stop behavior | No approximate frames or synthetic stability votes |
| Private assets | Existing restore tool/tests, separate bank and missing-lineage reporting | No private pixels committed; no source-session independence claim |
| Installation | Payload inventory verifier, C# ownership/OFF checks, existing upgrade/dependency contracts | No live clicking; real Windows acceptance not reproduced here |
| CI / documentation | Full mixed-dependency tests, isolated Runtime Vision, fatal lint/syntax, README and status drift | CI is not recognition accuracy |

The audit follows these critical paths and their automated tests; it is not a
claim to have manually proved every line or to have run physical Windows capture.

## Reproduced findings and fixes

### P1 — malformed scores could bypass identity rejection (fixed)

Before the fix, calling `identity_gate` with complete ordinary class support
returned `accepted` for NaN, positive Infinity, True and 1.5. In particular,
`nan < 0.82` is false. Separately `_component_confidence` converted NaN/Infinity
to 1.0 through clamping. This was a reproducible malformed-input boundary defect;
it is not evidence that the actual pixel classifier emitted those values.

Identity confidence must now be a finite numeric probability, excluding booleans;
malformed scores return UNKNOWN with `invalid_confidence`. Invalid threshold
configuration raises explicitly. Valid confidence 0.82 still passes the same
class/source-support rules. No numeric threshold, template, preprocessing or
confidence calibration changed.

The public adapter returns zero geometric confidence for nonfinite/bool input.
An explicitly invalid or below-threshold `tile_confidence` cannot be hidden by an
`accepted` string when importing hand/Gold identities. Legacy reports omitting
that optional score remain compatible; this does not invent a score for them.

### P1 — replay could silently finish a truncated range (fixed)

`iter_video_samples` previously broke on failed `grab`/`retrieve`; the caller
could summarize the successfully decoded prefix without indicating the requested
range was incomplete. It also sought directly to nonzero start ordinals despite
the existing documented VFR random-seek identity defect.

Sampling now advances sequentially from the beginning, including skipped frames
before the requested start. Premature decode/retrieve failure raises an explicit
frame-specific error and prevents a normal final summary. A user-requested stop
remains a distinct, non-error path. Starts beyond the recording are rejected
instead of silently clamped to its last frame. Sequential later-window access
can be slower; correctness of evidence IDs takes priority. This is a local-video
path, not a live capture speed claim.

Tests use synthetic capture doubles to verify sequential ordinals, early EOF,
pre-start failure, retrieval failure, natural completion, range errors and stop.
No unavailable original source was reconstructed or reused as a successful rerun.

### P2 — combined Vision test order leaked a temporary label reader (fixed)

The unmodified baseline with the available full Vision dependencies reported
1620 passed and one failure: a later real-bank test tried to load the earlier
fixture's nonexistent `templates/p1.png`. A module first imported while its label
dependency was patched retained the mock after the patch ended.

The symmetric-artwork test now resolves the consumer module before patching and
patches consumer transforms directly. It asserts the real label reader is
restored. The affected tests pass together in the previously failing order, and
the full combined suite passes. No production SIFT/ranking policy was changed.

### P2 — partial optional-dependency installs failed core tests (fixed)

Two experiment tests checked Pillow/numpy/sklearn but not their required OpenCV
dependency. In a host with some scientific libraries already installed and no
cv2, the advertised core-only route failed. Skip checks now cover the actual
optional dependencies. No needed production dependency was removed.

### P2 — Python optimization disabled some payload-verifier checks (fixed)

`verify_payload.py` used assertions for source hashes, approved assets, dataset
manifest and Executor OFF. `python -O` removes assertions. These checks now fail
explicitly, including exact boolean False for Executor. Subprocess tests run the
verifier under `-O` with altered source hashes and Executor enabled and require
rejection. The C# installer already separately checks OFF; this finding is about
the verification utility, not evidence of an enabled live Executor.

### P2 — status documents conflated history, rules and current usability (fixed)

README presented old 98% sample metrics under current ability, listed already
confirmed Kong scoring as unresolved, and suggested restarting strategy directions
outside the frozen frontier. PROJECT_STATUS had become a long historical narrative
and missed the latest private-candidate boundary. They now distinguish rule facts
from staged implementation, main from Draft, Runtime from private candidate, and
test success from real acceptance. Full regression instructions use pytest because
stdlib unittest does not collect function-style tests.

## Validation on the final local content

- Full `pytest -q tests` with Vision dependencies: **1634 passed**, **851 subtests passed**.
- Isolated Runtime Vision unittest suite: **141 tests passed**.
- Core-only stdlib unittest route with some optional scientific libraries but no
  cv2: **1541 tests run, 229 skipped, no failures**; this is not the full pytest suite.
- Fatal-error Ruff checks passed; tracked active Python syntax: **639 files, zero errors**.
- `git diff --check` passed. Initial malformed-input tests failed before repairs.

Final commit CI is separate from these local results. Inspect all five workflows
at the new SHA; do not transfer the green result of base 7f36538 to a new commit.
No current private video accuracy or real Windows UI/upgrade run was performed
locally. Existing Windows CI remains the packaging regression path.

## Remaining risks / acceptance work

1. Recover the exact complete first-hand query file before the third-checkpoint
   rerun. The historical truncated copy is not an equivalent source. The original
   user's recording is not declared damaged.
2. Opened yellow M4 evidence/recognition remains insufficient. Complete concealed
   identities alone cannot authorize shanten; own meld count must also be trusted.
3. Private support and rim/fallback improvements remain revealed development work,
   not installed baseline or independent generalization. Unknown original-match
   lineage must not be inferred from session names or derivative clips.
4. Qualify actual detector-path meld count/identity, then untouched original-match
   whole-hand evaluation and real Windows freshness/latency/recovery acceptance.
5. PR #126 remains very large. Prefer subsequent small, independently testable
   changes; do not merge, rebase or rewrite history merely as cleanup. The UI shell
   remains large, but extracting it now would add risk without fixing recognition.
6. No tracked LICENSE/COPYING file was found. License choice and permitted sharing
   of bundled gameplay imagery require an owner decision; this audit adds neither
   a license nor a claim about redistribution rights. Account secret-scanning and
   branch-protection settings were not verified by this source audit.

Frozen throughout: Agent V0.10, numeric identity threshold 0.82, unchanged valid
score/source gates, no private asset admission, Hint read-only, Executor OFF,
PR #126 Draft and unmerged. Rule revisions and simulator rewards are untouched.
