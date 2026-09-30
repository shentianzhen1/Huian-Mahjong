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

## Engineering decision

Add a separate deterministic
`public_meld_identity_normalization` layer after regular face splitting and
before identity feature extraction. Keep it development-only for now.

Do not:

- change the existing public identity score/margin gate;
- lower the concealed Runtime 0.82 threshold;
- wire the 12% candidate into Runtime/Hint/Executor by default;
- call 2/2 a validation accuracy result;
- count multiple hands/clips from one original match as independent evidence.

## Next evidence needed

Prioritize another independent original match containing already-covered meld
classes. The most useful classes are those currently supported by only one
match group, because one additional independent occurrence can make them
eligible for a new-match cross-group query.

Until then, the 12% inset remains a development candidate only.
