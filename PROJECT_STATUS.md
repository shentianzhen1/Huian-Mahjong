# PROJECT_STATUS — Current Snapshot

**Snapshot date:** 2026-10-06
**Execution truth:** GitHub Issues
**Rule truth:** RULE_STATUS.md / RULE_EVIDENCE_MATRIX.md
**History:** CHANGELOG.md

## Branch and release scope

- The [player-confirmed contract](references/rules/2026-10-06/player_confirmed_special_rules.md) in Draft PR #126 now has Sanjindao/Eight-Flower settlement APIs plus staged pre-Gold Eight-Flower choice, explicit candidate-flower consumption, forced no-Gold eighth-flower terminal and automatic dealer Tianhu `base×2`. Snapshot: `huian-target-2026-10-06-opening-r1`. This is a scripted-wall API with unknown hidden location; live still reads visible Gold/flowers. Non-Tianhu staged openings stop safely pending first-round Qiangjin/Tianting. In-play re-prompts, full simulator/live routing and complete installer behavior remain pending.

- Integration work lives on `integration/issue69-replay-stack-20260926` in
  Draft PR #117. It is unmerged; these draft features are not a main release.
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
full-match recovery. Windows live capture/freshness/recovery acceptance remains
pending. Linux CI does not prove Windows usability. See docs/issue69_alpha_build.md.

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

Preserve 144 tiles, no fifth copies, at most three playable Gold copies,
zero-sum two-player settlement, reproducible seeds and explicit UNKNOWN.
