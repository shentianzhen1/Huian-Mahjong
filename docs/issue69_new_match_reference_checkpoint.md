# New-match reference development checkpoint — 2026-10-04

The owner's new eight-hand recording supplies one additional original match,
not eight independent sources. The frozen samples are development references
with assistant visual labels, not owner adjudication or blind promotion data.
Runtime identity remains UNKNOWN and the 0.82 gate is unchanged; Executor is off.

## Fixed-reference transfer

The first experiment freezes 12 faces from the first previously pinned P1, N,
S1-containing, and S8-containing groups. Queries are 75 previously reviewed
manual crops from the older eight-hand recording. All query crops are SHA
verified; query-match aliases are collapsed and excluded. References and
queries use the same existing single-face normalization and frozen SIFT scorer.

| Old query class | One-other-match ranking after adding references | Two-other-match support |
| --- | --- | --- |
| N | 5/15 correct | Still unavailable |
| S1 | 15/15 correct | Still unavailable |
| S8 | 20/20 correct | 20/20 scorable and correct |
| S7, S9 | 5/5 each correct | 5/5 each scorable and correct |
| M9 | Unavailable in the 12-face experiment | Still unavailable |

The S789 query contains five correlated group frames, not five matches.
Existing public controls have no baseline-correct identity regressions in
either support mode. This does not establish automatic crop accuracy, a
calibrated probability, complete public-state readiness, or Runtime acceptance.

- [12-face reference pin](../references/vision/2026-10-04/new_match_fixed_reference_candidate_pin_v0_1.json)
- [Baseline versus 12-face transfer report](../references/vision/2026-10-04/new_match_fixed_reference_transfer_v0_1.json)

## M9 geometry and identity are separate

The generic detector misses the leftmost opponent M9 group in three reviewed
samples (73, 74, 75 seconds of segment04). At 74 seconds, its center falls below
the existing upper-group x guard and the whole group becomes a single-face
candidate. At 73 and 75 seconds, a brightness connection to an enlarged central
tile produces a merged component instead.

`public_meld_top_row_peer_probe.py` is an optional offline experiment. Two
existing upper-group peers define a shared body band. Within that band it
requires compatible dimensions, nearby spacing, and no duplicate existing
group. Without two suitable peers it abstains. It does not replace the generic
detector and has no Runtime caller.

On these three samples it recovers bbox `[479,12,70,31]` and nine visible crops
without a manual crop boundary. The three timestamps are inspected development
checks; pixel-exact polygons and other layouts remain unverified.

Freezing three M9 faces from 73 seconds adds class support for the old M9 queries
but gives **0/15 correct identities**: 12 rank as M4 and 3 as M6. The 15-face
reference experiment retains the S1/S8 results and adds no public-control
regressions. M9 and N identity remain blockers; do not promote these references
or the geometry probe on the basis of source support alone.

- [Geometry report](../references/vision/2026-10-04/new_match_m9_row_peer_geometry_v0_1.json)
- [15-face reference pin](../references/vision/2026-10-04/new_match_fixed_reference_candidate_pin_v0_2.json)
- [12 versus 15 reference transfer report](../references/vision/2026-10-04/new_match_fixed_reference_transfer_v0_2.json)

## Validation and next step

34 focused tests pass across detector calibration, meld normalization,
body context, face segmentation, and the new peer probe. The four new tests
cover leftmost recovery with/without a touching animation, missing peers,
distant bright components, and duplicate prevention. Generic detector inputs
remain unchanged. Synthetic tests do not establish real-video recall.

## Resolution and digit-feature follow-up

The old N/M9 crops visually retain the named glyphs. The next comparison keeps
the same reference frames and projects their frozen automatic 1046x480 crop
boxes into the 2796x1290 native frame; it does not search for new boundaries.

| Candidate | N | M9 | Material regression or limit |
| --- | --- | --- | --- |
| Downsampled references, existing geometry | 5/15 | 0/15 | Prior development baseline |
| Native references, existing geometry | 14/15 | 0/15 | S1 drops from 15/15 to 14/15 |
| Native references, global 72x96 aspect | 15/15 | 0/15 | M6 and P8 public controls regress; reject global use |
| Native references, upper-half 72x96 feature within Wan | Not tested | 15/15 | Suit is specified by review; not 34-class recognition |

The within-Wan candidate reuses the existing fixed 0.5 upper fraction, applies
the same transform to references and queries, and retains the frozen SIFT
extractor/scorer. A reverse-source check uses all three old M9 faces from
already pinned frame 4794 as references and the three new native 73s faces as
queries; all three rank as M9 after excluding new-match templates. M4/M5/M6
controls remain 3/3. These are correlated, previously inspected samples.

Retain this as a limited digit-feature experiment. Neither global aspect
normalization nor wholesale native-reference substitution is admitted. Suit
recognition, M8 support, another other-original-match reference for N/M9, and
automatic old-query crop validation remain unresolved. SIFT ranks are not
Runtime confidence and do not open advisory capabilities.

- [Native pixel reference pin](../references/vision/2026-10-04/new_match_native_reference_candidate_pin_v0_1.json)
- [Resolution and within-Wan diagnostic](../references/vision/2026-10-04/new_match_north_wan_resolution_feature_diagnostic_v0_1.json)

## Automatic family-route falsification

The next offline evaluator removes the reviewed family from routing. It uses
the unchanged whole-face source-disjoint SIFT winner to propose M/P/S/HONOR;
only an M winner enters the fixed upper-half 72x96 Wan digit head. An absent
winner abstains. No confidence or margin threshold was fitted.

At one-other-original-match support, family ranking is correct on 73/75 old
manual crops, 21/21 public controls, and 15/15 recovered private controls. The
two old-crop errors are N at frame 3606 face 0 and S1 at frame 3606 face 1;
both enter the Wan head and rank as M5. All 15 old M9 crops still rank as M9
after routing, but that success does not cure false routes from other families.

Broader private Wan queries have four eligible true-class identities, all
four correct. Five other Wan queries lack a true-class reference from another
original match (M1/M2/M3/M7); their forced winners are not counted as supported
identity errors. The report records this separately for every query and both
support modes. The two-other-match setting does not supply a reliable family
gate: 20/60 old non-Wan crops route to Wan while classes lose source support.

An existing approved M8 **draw-region** crop is a stress query only. It is
excluded from templates and is not public-meld evidence. Whole-face ranking
proposes Wan (M4); the digit head ranks M9 while M8 is unsupported. This catches
a missing-class failure, not a measured M8 public-meld error rate. Its original
match lineage is unresolved; no independent-source qualification is claimed.

**Reject winner-family routing as an automatic identity gate.** Frozen SIFT
returns a winner even for unsupported classes and supplies no calibrated
abstention. Keep the Wan digit result diagnostic-only and preserve Runtime's
missing-class fail-closed behavior. Do not select a new margin threshold on
these inspected failures.

The evaluation verifies native reference pin equality, query/crop hashes,
public/private source registries, and original-match alias exclusion. It
inherits the earlier video-hash audit rather than rehashing videos. All 27
existing SIFT/private-loader/Runtime-reader tests pass. Runtime remains at 0.82;
Executor remains off.

- [Family-route ledger](../references/vision/2026-10-04/new_match_family_route_falsification_v0_1.json)
- [Offline evaluator](../workspace/vision/evaluate_new_match_family_route_probe.py)

Next use a separately supported, abstaining family observation and obtain
public-meld M8 references from another original match. Preserve these inspected
failures as regression controls; future blind promotion evidence must be new.

## Lower-feature consensus: abstention gain and reverse failure

This second candidate freezes a lower-half 72x96 feature before evaluation.
The lower-feature bank pools templates into WAN/NON_WAN and counts original
matches across tile classes. Both binary alternatives must be eligible; ties,
missing winners, and disagreement with whole-face ranking produce UNKNOWN.
No learned score/margin threshold or fraction search is used. The two feature
views share pixels and are not independent corroborating evidence.

At one-other-original-match support:

| Query packet | Correct binary family hypotheses | UNKNOWN | Wrong hypotheses |
| --- | --- | --- | --- |
| Old manual crops, 75 faces | 63 | 12 | 0 |
| Public controls, 21 faces | 21 | 0 | 0 |
| Recovered private controls, 15 faces | 15 | 0 | 0 |
| All frozen new native faces, reverse direction, 15 faces | 9 | 6 | 0 |
| M8 draw-domain stress only, 1 face | 1 | 0 | 0 |

The old N/S1 false routes now abstain; ten other old non-Wan crops also abstain.
All 15 old M9 queries still enter the diagnostic digit head and rank as M9.
Reverse queries exclude every template from the new recording's original
match, including references from its other segments. This is previously
inspected development data, not blind evidence.

Reverse M9 family recall is only **1/3**: two native faces abstain; one enters
the diagnostic digit head and ranks as unsupported M7, since new-match M9
references are excluded. Visual review of all three raw/normalized/lower crops
shows that the fixed lower half mainly contains the gray side wall and almost
none of the red Wan glyph. It is a body-fraction feature, not glyph localization.
Do not tune the fraction on these exposed failures.

The two-other-match mode remains rejected: it has eight incorrect NON_WAN
hypotheses in private controls, three in public controls, and one false WAN
hypothesis among new reverse queries. Zero old-packet false WAN routes alone
would conceal these failures. The ledger reports wrong hypotheses separately
from abstentions and missing true-class support.

M8 still enters the digit head and ranks as unsupported M9. Every query has
zero other-original-match M8 support. The evaluator records per-class source
support for the entire M1–M9 alphabet, and leaves `qualified_identity=null`
for every row. Hypothesis agreement does not bypass incomplete classes or
uncalibrated scores. No Runtime caller or threshold change is introduced.

32 focused tests pass, including five consensus/source-support tests covering
disagreement, missing competition, ties/missing observations, family-only
output, and same-original/exact-SHA exclusion with duplicate-match counting.

- [127-face consensus ledger](../references/vision/2026-10-04/new_match_lower_family_consensus_v0_1.json)
- [Evaluator with optional `--lower-family-consensus`](../workspace/vision/evaluate_new_match_family_route_probe.py)

Next validate automatic front-face-plane localization before extracting a Wan
glyph feature. Retain the fixed-fraction failure as a regression, and keep M8
public-meld source coverage and future blind qualification as separate gaps.

## Vertical front-band geometry checkpoint

`public_meld_front_band_probe.py` is a narrower first step, not complete plane
rectification. Existing single-face normalization precedes it. The frozen
low-saturation light-body mask supplies brightness samples; Otsu separates two
brightness populations. A minimum 20-level median contrast, one wide bright
component, and a darker lower band are required. It preserves X and the entire
upper crop, trimming only the lower side wall with the existing two-pixel
context. Missing/ambiguous evidence abstains; no fixed-ratio fallback exists.

On the same 15 frozen native faces it produces 12 candidates and 3 abstentions;
on the old 75 manual crops it produces 70 candidates and 5 abstentions. These
are **candidate counts, not accuracy**. All 90 before/after pairs were visually
reviewed: no obvious added glyph clipping was seen in the 82 candidates.
The three native M9 and fifteen old M9 crops retain both visible glyphs after
most of the lower gray side wall is removed. This is assistant review without
pixel-exact ground truth, not owner adjudication or blind validation.

The eight abstentions are native S2/S1/S9 and the five old S9 frames. Their bright
front component is absent/ambiguous under the frozen criteria; keep UNKNOWN.
This experiment does not certify their full upstream crop boundaries or solve
slanted plane edges, shadowed faces, arbitrary orientations, or STACKED crops.
Two original matches remain two matches, despite ninety face rows.

42 focused tests pass, including six new cases: dark side-wall trimming with
glyph retention, uniform/weak-contrast faces, reversed brightness layout,
tiny/empty crops, and ambiguous multiple bright components. Runtime/consensus
and existing geometry/symmetric-normalization checks remain passing.

- [Geometry ledger](../references/vision/2026-10-04/front_band_geometry_probe_v0_1.json)
- [Visual review bound to the ledger hash](../references/vision/2026-10-04/front_band_visual_review_v0_1.json)
- [Offline geometry evaluator](../workspace/vision/evaluate_front_band_geometry_probe.py)

Next apply the frozen band transform symmetrically to reference and query
features, explicitly retaining band failures as abstentions rather than old
feature fallback. Then repeat family/identity controls and reverse-source M9
checks. No identity improvement is claimed by this geometry-only checkpoint.

## Symmetric front-band feature comparison: reject global replacement

The optional evaluator path applies the frozen band transformation to BOTH
references and queries before all three features. Band failures return no
descriptors and no raw-feature fallback. The strict private loader first verifies
the unchanged original ZIP/manifests/crops; alternate private features are then
computed from the verified bytes with explicit abstention records. Its existing
verification contract is not relaxed to hide geometry failures.

All 127 queries remain paired with the prior consensus ledger. At one-other
original-match support, the old packet's correct binary hypotheses drop from
63/75 to 51/75. Ten S1 crops newly route to Wan. Its entire 15-face S1 identity
support and five S9 queries lose eligible true-class support, since shadowed
native S1/S9 references cannot supply front-band features. Public controls drop
from 21/21 to 18/21 correct binary hypotheses; private controls from 15/15 to
12/15. Public and private M6 digit controls each lose a previously correct
result. Coverage loss and abstention stay in every denominator.

The unaugmented reverse packet now routes all three native M9 faces to Wan,
but true M9 identity is still unscorable once their own new match is excluded.
A separate paired reverse experiment adds the SAME three previously frozen old
M9 faces from frame 4794 to both configurations. With those fixed references:

| Native reverse M9, one other original match | Prior body features | Symmetric front-band features |
| --- | --- | --- |
| Family route and supported M9 digit winner | 1/3 | 3/3 |
| Other faces | 2 UNKNOWN family hypotheses | 0 |

Old 15-face M9 queries remain 15/15 in both configurations because their own
old-match additions are excluded. All new-match templates are likewise excluded
for native reverse queries. Three correlated faces do not constitute three
independent sources. Two-other-match M9 qualification is still absent.

**Reject global front-band feature replacement.** Retain only the geometry and
limited M9 numeral diagnostic; the local reverse gain does not outweigh false
family routes, coverage losses, or control regressions. M8's new UNKNOWN is a
band failure, not successful M8 recognition. All qualified identities remain
null, Runtime stays at 0.82, and Executor remains off.

53 focused tests pass, including strict role-symmetric feature preparation,
no raw fallback, and paired-ledger tests preventing source/crop mismatches or
dropped queries from hiding abstention/coverage regressions.

- [Symmetric front-band ledger](../references/vision/2026-10-04/new_match_symmetric_front_band_v0_1.json)
- [Paired comparisons, fixed reverse pins and per-query outcomes](../references/vision/2026-10-04/new_match_front_band_identity_paired_comparison_v0_1.json)
- [Paired report evaluator](../workspace/vision/compare_front_band_identity_reports.py)

Next recover front-band coverage on the shadowed S1/S9 references and preserve
explicit missing-class abstention. Keep the previous whole/lower feature bank
as the development baseline until family-route regressions are resolved; do not
adopt the new transform globally or fit a threshold on these revealed failures.

## Overlapping bright fragments: partial S1 coverage recovery

The native S1 bird glyph separates its bright face into two connected components
whose original bounding boxes overlap. An explicit offline
`--front-band --merge-front-overlaps` option joins only groups connected by
strictly overlapping ORIGINAL component envelopes. Touching edges, gaps and
new overlaps introduced only by a union envelope do not join. The default
strict transform and brightness/contrast requirements are unchanged. Queries
and references use the same preparation; failed bands still have no fallback.
Visual review of the recovered S1 band retains the bird glyph and removes the
lower side wall. This is a revealed development repair, not blind evidence.

All 127 source/crop-pinned query rows remain paired. The restored strict run
reproduces every previously published query mode exactly. At one-other-original
support:

| Packet / measure | Strict front band | Overlap option |
| --- | --- | --- |
| Old 75-face packet: correct binary hypotheses | 51/75 | 61/75 |
| Old packet: false Wan routes, all S1 | 10 | 0 |
| Old packet: unscorable true-class identities | 20 | 5 |
| Old M9: supported digit winners | 15/15 | 15/15 |
| Public controls: correct binary hypotheses | 18/21 | 18/21 |
| Private controls: correct binary hypotheses | 12/15 | 12/15 |

There are no additional paired family/digit regressions or support losses in
this option, at either one- or two-other-match support. Two-other-match outcomes
are unchanged: recovering a face from the same new match adds no second source.
Native S2 (`S1_1.png`) and S9 (`S8_2.png`) still abstain on whole/lower features;
the old packet's five S9 queries still lack true-class support. Native reverse
M9 identity remains unscorable without the separate frozen old-M9 additions.
All qualified identities remain null.

This only recovers the missing S1 reference. Correct binary hypotheses still
fall short of the prior body-feature baseline (63/75, 21/21 and 15/15), and M6
control coverage/digit losses remain. Reject global front-band replacement.
Runtime remains 0.82; Hint/Executor integration remains disabled for this probe.
55 focused tests pass, including the empty-corner case preventing union-created
bridges. The core-only run passes three comparison tests and skips nine optional
Vision tests.

- [Overlap-option ledger](../references/vision/2026-10-04/new_match_front_overlap_merge_v0_1.json)
- [All-query paired comparison](../references/vision/2026-10-04/new_match_front_overlap_paired_comparison_v0_1.json)

Reproduce the paired comparison with
`python -m workspace.vision.compare_front_band_identity_reports --overlap-only`
and `--baseline`, `--front`, `--output` pointing to the strict ledger, overlap
ledger and comparison respectively. Reproduce the overlap ledger with the same
verified ZIP inputs as the strict evaluator plus `--merge-front-overlaps`.

Next inspect the unresolved dark S2/S9 face-plane evidence and M6 control
failures separately. Do not lower brightness thresholds or infer identities
from a missing class; retain the prior body-feature bank as the baseline.

## Same-frame bracketed geometry: recover shaded middle faces, retain regressions

The remaining M6 control loss has two linked causes. The private M6 query
fails the brightness-band transform, and removing that same private reference
leaves the public M6 query without an eligible other-match M6 reference.
Its whole-face winner becomes M3 and its digit winner M5. This is missing
true-class coverage, not evidence that the visible tile changed identity.
The private normalized M6 already ends near the front/side boundary: adding
another arbitrary lower crop would risk removing the artwork.

A separate optional probe uses two independently successful SAME-FRAME
neighbor band boundaries in source coordinates. It permits only a target
bracketed on both sides by adjacent peers of the same level row and source
crop height, with an exact zero-rotation coordinate mapping. A steep boundary
slope, missing/ambiguous peer, different row, edge extrapolation, invalid pixel
bounds or conflicting source/frame/match provenance abstains. Brightness gates
and direct candidates are unchanged. If normalization has already removed the
side wall, the whole normalized body can be retained only when the peer plane
bound supports it; failed geometry never falls back to raw features.

The source-pinned geometry packet keeps all 105 manually split crops:

| Packet | Direct overlap-band candidates | Bracketed candidates |
| --- | --- | --- |
| Native 15 faces | 13/15 | 14/15 |
| Recovered private 15 controls | 12/15 | 14/15 |
| Old 75-face packet | 70/75 | 70/75 |

The three new candidates are native S2, private P8 and private M6. Visual
review of source/prepared pairs retains their full glyphs without obvious new
clipping. These counts are geometry availability, not accuracy. Native S9 and
the five old S9 faces are at row edges and remain UNKNOWN; private P3 also lacks
a valid two-sided bracket. Automatic detector/splitter success is not claimed.

The opt-in `--bracketed-peer-band` identity experiment applies the same
preparation to references and queries. An in-memory query ID plus exact source
SHA binds the crop to its verified source-frame row. Pixel equality alone
cannot borrow another recording's peers. Missing/ambiguous context keeps the
direct transform, including its failure; it supplies no raw-feature fallback.
Public controls have no added neighbor context. Their source-disjoint ranks
can change only through the verified reference availability changes.

Both comparisons retain all 127 query IDs, source/crop pins and abstentions:

| One-other-match development measure | Overlap only | Bracketed |
| --- | --- | --- |
| Native reverse: correct binary hypotheses | 10/15 | 11/15 |
| Private controls: correct binary hypotheses | 12/15 | 14/15 |
| Public controls: correct binary hypotheses | 18/21 | 18/21 |
| Old packet: correct binary hypotheses | 61/75 | 61/75 |
| Public/private M6 supported digit winners | 0/2 | 2/2 |
| Old M9 supported digit winners | 15/15 | 15/15 |

There are no new one-other-match family or digit regressions against overlap
only. At TWO-other-match support, however, native reverse correct binary
hypotheses fall from 7/15 to 5/15. `native_reverse_P1_0` and `_1` change from
NON_WAN to UNKNOWN: restored M6 references make M6 the whole-face winner,
while the lower feature still chooses NON_WAN. They are correlated faces from
one match, not two independent failures. Consensus correctly abstains rather
than issuing a false Wan route. Private two-source hypotheses improve 4/15 to
5/15; other packets are unchanged. This loss remains in the published paired
ledger rather than being hidden by the single-source gains.

**Keep this as a geometry/identity diagnostic, reject global replacement.**
Against the prior body-feature baseline, one-source old/private/public correct
binary hypotheses still fall from 63/75, 15/15, 21/21 to 61/75, 14/15, 18/21.
No supported digit winner regresses against that baseline, but public-state
coverage is still incomplete. Native reverse M9 identity is still unscorable
without the separate old-M9 additions. All qualified identities remain null;
Runtime stays 0.82; Executor remains off. This revealed experiment is not a
blind promotion batch.

64 focused tests pass, including source/frame/match separation, equal pixels
with a different source/row, ambiguous contexts, missing and distant neighbors,
sloping boundaries and glyph retention. Core-only tests pass three comparison
tests and skip 18 optional Vision tests.

- [Bracketed geometry probe](../workspace/vision/public_meld_bracketed_front_band_probe.py)
- [105-face geometry ledger](../references/vision/2026-10-04/new_match_bracketed_front_geometry_v0_1.json)
- [127-query identity ledger](../references/vision/2026-10-04/new_match_bracketed_front_identity_v0_1.json)
- [Paired comparison against overlap and body baselines](../references/vision/2026-10-04/new_match_bracketed_front_paired_comparison_v0_1.json)

Reproduce geometry with `python -m workspace.vision.evaluate_bracketed_front_band_probe`
and the same four verified ZIPs. Reproduce identity with the frozen family
probe plus `--lower-family-consensus --front-band --merge-front-overlaps --bracketed-peer-band`.
Reproduce comparisons with `python -m workspace.vision.compare_front_band_identity_reports`
plus `--bracketed-peer --body-baseline` (prior body ledger), `--baseline`
(overlap ledger), `--front` (bracketed ledger) and `--output`.

Next address edge-face S9 geometry using visible source-plane evidence; do not
extend this bracket helper by guessing beyond its neighbors. Keep remaining
P3/P5/S5/S2 control failures and two-source family availability visible.
