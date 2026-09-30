# Public Meld Identity-Face Normalization V0.1

Date: 2026-10-01  
Issue: #69  
Scope: development-only identity-domain experiment

## Question

After exposed-meld group detection, geometry normalization, and regular
three-face splitting are already successful, is the remaining identity failure
primarily caused by the classifier family or by excess border / crop-domain
mismatch between normalized query faces and the reviewed public-meld template
faces?

## Frozen upstream observation

The earlier concealed-template transfer experiment remains rejected:

- reviewed regular meld groups reaching classifier input: 7/7
- normalized faces reaching classifier input: 21/21
- raw exact result when reusing concealed templates: 6/21
- accepted at the unchanged concealed Runtime 0.82 gate: 0/21

Do not lower 0.82 and do not reuse concealed templates for public meld identity.

## Source-disjoint development query

The current public-meld development bank has 21 approved face labels covering
17 tile classes and four independent original-match groups. Only P6 and S4 have
support from at least two independent *other* match groups for a genuinely new
query match.

The locked first-hand query set contains two query-only crops:

- P6
- S4

The query match group is excluded from the template bank. Query crops are never
training-template eligible.

## Feature A/B

Without an identity-specific inset:

| feature | P6 | S4 | top-1 |
| --- | --- | --- | --- |
| legacy public gray | wrong | wrong | 0/2 |
| gray + edge | correct | wrong | 1/2 |
| Lab chroma + edge | correct | wrong | 1/2 |

With a 12% center inset applied **only to the already-split query face** before
feature extraction:

| feature | P6 | S4 | top-1 |
| --- | --- | --- | --- |
| legacy public gray + 12% inset | correct | correct | 2/2 |
| gray + edge + 12% inset | correct | wrong | 1/2 |
| Lab chroma + edge + 12% inset | correct | wrong | 1/2 |

For the legacy-gray + 12% development variant:

- P6 winner P6, margin ~= 0.065538
- S4 winner S4, margin ~= 0.219742

## Interpretation

The strongest current signal is **not** a more complex feature family. It is a
query/template crop-domain mismatch. A small inner-face normalization can make
the same conservative gray feature rank both currently eligible first-hand
queries correctly.

This does **not** establish an accuracy rate. The 12% inset was selected after
inspecting these same two development queries, so the 2/2 result is in-sample
development evidence and cannot justify Runtime promotion or a new confidence
threshold.

## Private tight-crop negative control

A pre-existing private review package containing 36 already-tight approved face
crops from 12 groups / two original matches was restored locally. No private
pixels, source hashes, room/player metadata, or crop registry were added to the
public repository.

Using the unchanged legacy gray feature and keeping templates unmodified:

- same-original-match, cross-clip queries with another same-class reference:
  baseline **6/17** top-1; query-side 12% inset **4/17** top-1;
- the one shared cross-original-match S4 query ranked **33/33** in the opposite
  33-face gallery at baseline and **22/33** after query-side 12% inset, but its
  matching score dropped from about **0.180** to about **-0.010**;
- in the reverse 3-face gallery, the matching S4 remained **3/3** and its score
  also decreased.

This is a useful negative control: the 12% transform is **not** a generally
better public-meld preprocessing rule. It appears useful specifically as a
candidate compensation for query crops with excess outer border. Already-tight
reviewed template crops must stay unchanged.

These checks remain development-only and are not accuracy or promotion
evidence.

## Engineering decision

Add a separate deterministic
`public_meld_identity_normalization` layer after regular face splitting and
before identity feature extraction, but scope it explicitly to the **query
side**. Keep it development-only for now. The reviewed template bank must not
pass through this 12% transform.

Do not:

- change the existing public identity score/margin gate;
- lower the concealed Runtime 0.82 threshold;
- apply the 12% transform to the reviewed template bank or already-tight crops;
- wire the 12% candidate into Runtime/Hint/Executor by default;
- call 2/2 a validation accuracy result;
- count multiple hands/clips from one original match as independent evidence.

## Next evidence needed

Prioritize another independent original match containing already-covered meld
classes. The most useful classes are those currently supported by only one
match group, because one additional independent occurrence can make them
eligible for a new-match cross-group query.

Until then, the 12% inset remains a development candidate only.
