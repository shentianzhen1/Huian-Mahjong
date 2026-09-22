# Public Identity Shadow V0.1

Date: 2026-09-22  
Issue: #69  
Status: development diagnostic; naive cross-region template reuse rejected

## Question

Can the existing Runtime Vision hand / draw / global template classifier be
reused directly to identify public discard tiles?

V0.1 tested five reviewed public discard identities:

- P1
- S9
- N
- M4
- P7

For each sample the classifier was tested on:

1. the pixel-reviewed truth bbox;
2. the Public Tile Detector best candidate bbox;

and in three template modes:

- global templates;
- `hand_region`;
- `draw_visual`.

## Result

| Crop | Template mode | Correct | Accuracy | Avg confidence |
| --- | --- | ---: | ---: | ---: |
| detector bbox | draw_visual | 0/5 | 0% | 0.320743 |
| detector bbox | global | 0/5 | 0% | 0.359319 |
| detector bbox | hand_region | 0/5 | 0% | 0.350665 |
| truth bbox | draw_visual | 0/5 | 0% | 0.347240 |
| truth bbox | global | 2/5 | 40% | 0.393534 |
| truth bbox | hand_region | 3/5 | 60% | 0.379249 |

The practical path — detector bbox into an existing template mode — failed all
five reviewed public identities in every mode.

Examples:

- public S9 was predicted as S6 / M4 / M5 depending on mode/crop;
- public N was predicted as E or G;
- public M4 is correct with the reviewed truth bbox in global/hand mode, but
  becomes M1 on the detector bbox;
- public P7 is correct only with the reviewed truth bbox in hand mode; the
  detector bbox becomes P1 / G.

The exact per-sample diagnostic values are archived in:

`references/vision/2026-09-22/public_identity_shadow_v0_1.json`

## Important limitation: source-session exclusion was ineffective

The experiment attempted to remove templates whose:

`source_session || source_id`

exactly equalled the calibration sample's source session.

For all five samples:

    excluded_same_session_labels = 0

The existing runtime-template session identifiers therefore do not match the
public calibration session names.

This means the experiment is **not** a strict leave-session-out or leak-free
identity evaluation.

That limitation does not rescue naive template reuse. The relevant engineering
observation is that performance is already poor under this more permissive
setup:

- detector-bbox accuracy is 0/5 in all three modes;
- manually reviewed truth bboxes are still only 0–3/5;
- reported template correlations are low.

A future formal public identity evaluation still needs proper source lineage and
source-disjoint data.

## Decision

Naive cross-region reuse is rejected.

Do **not**:

- map Public Tile Detector candidates through `hand_region` and accept the
  result;
- map them through `draw_visual`;
- rely on the global template pool;
- lower the Runtime Vision identity gate to force public IDs.

Public Tile Detector candidates remain:

    tile_id = UNKNOWN

until a separate public-region identity path has enough reviewed evidence.

## Why a separate public-region dataset is needed

Public tiles differ from concealed-hand templates in several ways already
visible in the reviewed evidence:

- public response tiles may be enlarged;
- detector bboxes have different borders/padding than hand slots;
- small upper public tiles use a different scale;
- exposed meld faces can be shorter, compact, tilted, or stacked;
- replay/response UI can alter surrounding pixels.

These domain shifts are large enough that the current template normalizer does
not transfer reliably.

## Next implementation slice

Create a separate development-only public identity label schema rather than
modifying the existing hand/draw/gold label contract.

Recommended initial regions:

- `public_action` — enlarged / focused public tile candidates;
- `public_single` — smaller upper public tile candidates;
- `public_meld` — individual exposed meld faces after face segmentation.

The first label set may use already-reviewed sources for development, but must
remain excluded from formal Vision promotion.

The initial five public discard identities are nowhere near enough for a full
34-class public identity gate. The goal of the first label slice is to prove the
data loop and region separation, not to claim complete public recognition.

Executor remains off.
