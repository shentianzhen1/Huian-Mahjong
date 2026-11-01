# Unified clean-training paired replay — 2026-10-25

Both modes now use the same137-label bank after excluding the ten previously
reviewed bad crops. Baseline uses installed packet2026.10.25.5; candidate adds
only the private W3180/M3 4860 references. Same237 endpoints, sequential decode,
actual UI worker and advisory pipeline, source trial enabled, no manual Gold.

| Mode | Displayed shanten | Discard windows | Geometry-untrusted displays |
| --- | ---: | ---: | ---: |
| Clean baseline | 171/237 | 40 | 0 |
| Clean candidate | 172/237 | 41 | 0 |

Only frame228 is newly accepted. No accepted window is lost, no existing
advice changes, and all previously accepted hands/advice match their respective
raw-bank runs. Frame48(opening conflict),612(count transition),1776(low-score
raised M3) and the terminal Hu region remain blocked. Source RGB hashes match
between paired runs. Frame228's17-tile endpoint review remains valid; it is
not a complete reannotation of the earlier burst frames or every accepted hand.

The134-query clean controls from the preceding experiment use the same ten-image
exclusion policy, holding out known original matches or exact unresolved source
SHAs. Baseline105→candidate110 top1 correct;89→93 scores>=0.82; wrong high scores
1→0. These are developmental crop controls, not independent match qualification
or calibrated confidence. They can now be considered alongside a full replay
using the same clean-label policy, while their held-out training splits remain
explicit. No Windows capture or worker-scheduled latency acceptance is claimed.

Added `with_reviewed_training_exclusions` in the explicit offline module
`experimental_training_review.py`. It verifies registry authority, relative
paths, source/tile identity and actual file hashes before rebuilding classifier,
coverage and Gold-skin facts together. It returns new resources, preserves prior
session exclusions and stops on empty banks or inconsistent review evidence.
It does not modify approved labels/assets or wire itself into Runtime defaults,
UI or the installed packet. Real dataset feature arrays were checked equal to
the paired replay's temporary clean-bank construction.

Offline usage before adding experimental references:

```python
from workspace.vision.tiles_runtime_v0_2.runtime_reader import prepare_runtime_resources
from workspace.vision.tiles_runtime_v0_2.experimental_training_review import with_reviewed_training_exclusions
resources = prepare_runtime_resources(dataset_root, source_session)
resources = with_reviewed_training_exclusions(resources, review_registry_path)
```

Final validation:28 focused tests,25 Runtime reader tests and5 bundled-reference
tests passed; syntax and diff checks passed. No full suite rerun. CI must be
checked at the resulting commit.

Threshold0.82, AI V0.10, read-only Hint, Executor OFF, Draft/unmerged PR and
installed bundle2026.10.25.5 remain unchanged. M3 raised identity and independent
whole-hand validation remain unresolved. No private pixels added to GitHub.
