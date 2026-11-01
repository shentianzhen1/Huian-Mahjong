# Advice recovery development audit — 2026-10-25

At `f56b5e7`, sequentially decoded the same SHA-locked October 12 recording.
Used the actual UI `_runtime_worker`, its parallel two-frame classification,
`eligible_prior_identity`, and `RuntimeAdvicePipeline` with reference version
2026.10.25.5. No manual Gold; explicit hand/Gold source trial enabled. Samples
are six decoded frames apart; worker endpoints are every twelve frames at
nominal 30fps. This fixed source-clock experiment ignores worker duration and
is neither the earlier dynamic scheduled replay nor Windows UI acceptance.

237 windows produced 171 displayed structural suggestions and 40 post-draw
windows with discard candidates. First advice was at frame84 /2.8s source time.
27 accepted→blocked→accepted runs recovered, with a median0.4s and maximum2.4s
from the first blocked endpoint to the next accepted endpoint. No geometry-
untrusted window displayed advice. These are overlapping windows, not hands,
independent accuracy or independently reviewed correct advice.

Twelve geometry-trusted windows still blocked. Eight occur at2736–2820 after
an explicitly visible Hu overlay and exposed opponent hand; the terminal blocked
run starts at91.2s and is not a continuing-play recovery failure. Frame612
shows hand rearrangement with a raised tile, so count rejection is appropriate.
Frame48 is an opening Gold conflict. The remaining frame228/1776 checkpoints
contain low-score raised-tile confusions: W→E at0.400603 and M3→S2 at0.556055.
Both remain UNKNOWN. The next useful experiment is raised-tile appearance/crop
validation, preserving0.82 and fresh-frame confirmation. Do not relax geometry
or counts to erase transition pauses. Unknown meld faces/public rivers still
block public remaining-copy and danger capabilities, independently of shanten.

Measured host worker median429.6ms and empirical p95≈1116.1ms. The median
exceeds the fixed400ms launch spacing, so these replay timestamps cannot prove
that all opportunities finish in real time. Host timing is environment-specific;
use single-flight scheduled simulation or Windows capture for latency claims.

20 focused confirmation/freshness/worker regressions passed. An initial command
named a nonexistent test module; corrected module names all passed. No Runtime,
AI, template, threshold or Executor behavior changed. No private pixels added.
The metadata file retains run boundaries, selected source RGB hashes, raw gate
reasons and rejected components. It does not relabel trial results as strict
source-qualified acceptance or formal promotion evidence.
