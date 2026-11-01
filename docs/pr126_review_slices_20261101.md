# PR #126 review slices — 2026-11-01

Execution ownership: [#45](https://github.com/shentianzhen1/Huian-Mahjong/issues/45)
and [#7](https://github.com/shentianzhen1/Huian-Mahjong/issues/7).
This is a frozen review inventory, not another execution backlog.

Audited PR head `adc4fc1e72319fda5b121a2ddf909161f3fce87e`,
base main `da07055b286e26164fe8e3da9ec2f0da8609c899`:
665 changed paths, 136619 additions, 936 deletions.
All seven API pages (100 × 6 + 65) were read; counts are not a current-head promise.

| Review area | Paths |
| --- | ---: |
| other | 6 |
| delivery_ci | 14 |
| documentation | 77 |
| assets | 46 |
| rules_environment_simulator | 23 |
| evidence_metadata | 86 |
| tests | 219 |
| hint | 23 |
| vision | 171 |

The mutually exclusive classification uses docs/ or Markdown first, then
references/, tests/, dataset/, Hint, Vision, Rules/Environment/Simulator,
packaging/CI and remaining paths. Counts total 665. These are review areas,
not verified independent merge units. Tests must follow the code they verify.

## Concrete extracted slice

Draft [#147](https://github.com/shentianzhen1/Huian-Mahjong/pull/147) targets main.
Head `a0d6c6663079fec23f44937db91df11a65dc9389`, 10 added paths:
5 Markdown records and 5 JSON metadata records. Every blob is identical to
the audited #126 source, and all paths were absent from the fetched main tree.
The five JSON files parse. No code execution tests were run locally.

- `docs/vision/new_recording_frame_identity_20261013.md` — `98d3cd4b5d2f348e2504d8b4332110c3b704cada`
- `docs/vision/new_recording_exact_frame_rereview_20261013.md` — `e329061f93b2322b6057b3d9b79801e0c18478fa`
- `docs/vision/new_recording_crop_diagnostic_20261013.md` — `7d839c0cfff47d587b096962d034265ee8a9d059`
- `references/vision/2026-10-13/new_recording_review_selection_v0_1.json` — `05e78ed21aee634dc1851b3c8de05f6733d061e4`
- `references/vision/2026-10-13/new_recording_vfr_frame_identity_audit_v0_1.json` — `8ffc84c60b305ecc7f282e35698f2916a1b550c1`
- `docs/vision/uploaded_artwork_meld_probe_20261013.md` — `07d30ff106d487652bc0582cdf662c8c3d84b40d`
- `references/vision/2026-10-13/uploaded_artwork_meld_probe_v0_1.json` — `be70871dce7f532311d43fdd284aff3426c2a437`
- `references/vision/2026-10-13/uploaded_artwork_symmetric_normalization_v0_1.json` — `b09c0668e94b0a9ff9849f5e808362da80a219c1`
- `docs/vision/client_artwork_integration_20261013.md` — `24104249c38bf6c77e36297ca00e4c5e7fc76eba`
- `references/vision/2026-10-13/current_bank_client_intake_reconciliation_v0_1.json` — `ecf2b0955ee423ccdc0d899856351d20e74b13aa`

These records concern exact-frame correction, intake reconciliation and artwork
development experiments. Tools referenced by historical text may exist only
at the fixed source snapshot; archiving the evidence does not ship those tools
or promote a model. No pixels or new private identifiers are added.

Until #147 is separately reviewed and merged, these paths remain in #126.
Do not delete them from #126 to make the number smaller, and do not count this
preparation as a completed reduction. This update leaves both PRs Draft.

## Existing PR relationships

The API read before creating #147 found 11 open PRs, 8 Draft.
The chain #127 → #128 → #129 → #130 → #131 uses its predecessor as base
(#127 is based on #126). #135/#136 target the older integration branch.
#121/#122/#123 target main and have separate tool/docs/rule scopes.

No branch is closed, merged or retargeted by this change. Historical #126 body
analysis says #127–#131 retain unique changes; this run rechecked their refs
but did not redo their full content-equivalence proof. Do not auto-close them.
Remaining runtime slices require import/asset/test dependency review; broad
control-flow refactoring solely to split the PR is not justified.

## CI scope

The current Tests scope compares PR base to HEAD, so a documentation-only
increment on #126 still sees earlier code changes and runs the full matrix.
The standalone evidence slice offers a genuinely docs/evidence-only PR.
Retain full PR/pre-merge verification; do not skip it using only the last
commit's paths. No CI workflow or installer release request is changed here.
