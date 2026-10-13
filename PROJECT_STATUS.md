# PROJECT_STATUS — Current Snapshot

**Snapshot date:** 2026-10-13
**Execution truth:** GitHub Issues
**Rule truth:** RULE_STATUS.md / RULE_EVIDENCE_MATRIX.md
**History:** CHANGELOG.md

## Near-term user objective

Stable current hand / own exposed-meld observations -> structural shanten and
minimum-shanten discard suggestions, under Issues #69/#45. The current focus is
complete-hand acceptance and actual detector-path meld counts/identities,
not another Agent line or exhaustive action transcription.
See [2026-10-07 recognition audit](docs/recognition_shanten_audit_20261007.md)
for current support gaps, fixes and source-qualified acceptance measurements.
Live-only cross-burst identity confirmation blocks changed/missing observations;
frozen Runtime scoring and stateless replay remain separate. Full-bank concealed
coverage is 34/34, but only 22 classes have two stored source sessions; that
inventory is not independent-match accuracy. Full meld identity is not yet a
qualified live Runtime input. V0.10 unchanged; Executor OFF.

The [2026-10-13 reproduction](docs/vision/concealed_43of43_candidate_reproduction_20261013.md)
reproduced the development-only support + primary-first UNKNOWN tight-fallback
candidate: 43/43 ordinary tiles, 3/3 complete hand samples, zero wrong accepts.
The unchanged packaged Runtime remains 25/43 accepted and 0/3 complete hands on
that same diagnostic. Neither result is independent live accuracy. Candidate
fallback is not wired into Runtime; fresh original-match validation is pending.
The promotion-report input validation fix rejects malformed booleans, counts
and rates without changing the frozen thresholds. See the
[ordered audit follow-up](docs/ordered_audit_optimization_20261013.md).

Draft PR #138's verified development intake tool is now available on this Alpha
branch. Its private source evidence covers 34+8 client artwork classes and 79
recovered concealed crops; all 79 link to existing current-bank source records.
Artwork is not Runtime training/support admission and no new accuracy was
measured here. See [client intake alignment](docs/vision/client_artwork_integration_20261013.md).
The [private whole-hand artwork A/B](docs/vision/client_artwork_whole_hand_ab.md)
now verifies a manual truth lock and compares baseline/merged/primary-first
classifiers on identical crops without counting artwork as real support. Actual
private image-based evaluation remains pending; no accuracy gain is claimed.

A separate [uploaded contact-sheet meld probe](docs/vision/uploaded_artwork_meld_probe_20261013.md)
now compares six predeclared variants on 15 recovered, manually reviewed meld
crops from five groups within one original match. Artwork NCC recovered 8/15
identities versus real-hand NCC's 0/15, but fused SIFT did not exceed real-hand
SIFT's 8/15. This is development crop scoring, not live acceptance or a new
independent whole-hand evaluation. Runtime remains unchanged.
One fixed symmetric normalization follow-up improves rendered artwork SIFT
from 7/15 to 11/15 faces, with four gains and zero losses on the same revealed
crops; exact groups remain 2/5. Real-hand and fused paths show regressions, so
this is a separate development candidate and not a global Runtime transform.

## Branch and release scope

- The [player-confirmed contract](references/rules/2026-10-06/player_confirmed_special_rules.md) in Draft PR #126 now has Sanjindao/Eight-Flower settlement APIs plus staged pre-Gold Eight-Flower choice, explicit candidate-flower consumption, forced no-Gold eighth-flower terminal and automatic dealer Tianhu `base×2`. Snapshot: `huian-target-2026-10-06-opening-r1`. This is a scripted-wall API with unknown hidden location; live still reads visible Gold/flowers. Non-Tianhu staged openings stop safely pending first-round Qiangjin/Tianting. In-play re-prompts, full simulator/live routing and complete installer behavior remain pending.

- Active Alpha work lives on `codex/hint-alpha-local-test-sync-20261004` in
  Draft PR #126. Draft PR #117 is the earlier integration branch; neither is
  merged, and these draft features are not a main release.
- Draft package identity is `0.2.1`; CurrentAgent remains MeldAwareShantenAgent
  V0.10. RuleSnapshot is versioned independently from package and Agent.
- Issue #4 closed through PR #125 on main: only added kongs can be robbed;
  the failed kong leaves the original PENG and contributes no kong fan/fee.
  Rob-Kong uses ordinary Zimo x2 and normal dealer flow. Completed-kong tail Hu
  also uses ordinary Zimo x2 with additive completed-kong fan.
- This integration revision synchronizes the rule registry, special-outcome
  readiness, phase diagnostics and simulator terminal handling with those
  already-confirmed rules. It does not establish new gameplay evidence.

## Internal Alpha

Windows capture -> stable Runtime frames -> CurrentTableSnapshot -> independent
capability gates -> structural shanten / basic discard suggestions -> read-only UI.
Separate user-entered hand/Gold/own-meld-count input reuses the structural
capability gate without pretending to be Vision frames. Manual score before/
after entries for unresolved settlement rules are observed-only, zero-sum and
never invoke Environment settlement or official reward.
Use `START_HINT_ALPHA.bat --experimental` for explicit unpromoted internal advice.
Default mode retains the formal Vision promotion gate. Identity threshold 0.82;
Executor OFF. Capture/error/black-screen/epoch/freshness failures invalidate advice.

Own meld identity UNKNOWN may still permit structural shanten when hand, Gold
and own meld count are trusted. Missing public river/meld identities block live
remaining-copy and danger features. Dark-face fallback remains development-only.
Manual entries are unverified human assertions and cannot count as Vision
promotion or source-disjoint evidence.

Native private first-hand 173–176s replay now observes 8 structural advice
windows, 5 blocked windows and 1 recovery across 13 overlapping bursts. This
same-source smoke does not validate tile accuracy, strategic discard quality or
full-match recovery. Windows installed live-entrypoint smoke now passes in PR #126; actual
mirrored-game capture/freshness/recovery acceptance remains pending. Linux CI does not prove Windows usability. See docs/issue69_alpha_build.md.

An earlier same-original 160–164s source-locked replay adds two consecutive
automatic post-draw structural discard windows (M3/P5/P7/P9 tied at minimal
shanten). It proves the advisory pipeline can emit candidates, not that the
recognized identities or strategic ranking are human-confirmed.

## Remaining priorities

- #69: current-state advisory usability; offline public replay remains evidence
  and regression support, not an exhaustive eight-hand transcription prerequisite.
- #7: untouched source-disjoint evaluation against the frozen promotion gate;
  same-original-match clips and green CI do not establish generalization.
- #1/#2/#5/#9: implement the new player-confirmed contract and regressions as tracked by Issues; opportunistic direct-video corroboration remains separate.
- #6: preserve V0.10 and paired evaluation baselines; no new Agent in this work.
- #45: internal/read-only Alpha, evidence audit and Windows acceptance.

## Engineering checks

Core regression, Rules/Environment coverage floor 85%, Vision Regression,
Evidence Contracts, fatal-error lint and installed wheel boundary checks.
CodeQL analysis succeeded at the shared replay boundary head; GitHub secret
scanning/push-protection settings still require verification. Stop/recording
failures are visible and completion-write failures
remain retryable. Package-local test modules are excluded from runtime wheels.

The Windows test installer pins Python 3.14.7 and the runtime dependency versions
from the successful d492833 installer job. Build preflight and installed smoke
check these versions; the payload retains a hashed constraints file. Installer
CI applies to all PRs instead of only #126. See the
[dependency contract](docs/installer_reproducibility_20261013.md); actual mirrored
capture acceptance remains separate.

The installer now upgrades a fixed `current` directory and fixed desktop entry,
preserving shared evidence outside the replaceable program and archiving legacy
data before removing identified old versions. See the
[upgrade behavior](docs/installer_upgrade_behavior_20261013.md); actual Windows
EXE upgrade verification is part of the installer workflow.

Preserve 144 tiles, no fifth copies, at most three playable Gold copies,
zero-sum two-player settlement, reproducible seeds and explicit UNKNOWN.
