# Hint Alpha local test delivery — 2026-10-04

Execution issues: #45 (packaging/UI), #69 (snapshot advisory), #7 (independent Vision validation).

The current snapshot/shanten/manual-input bridge was integrated from development commit `bad588ef2e300b48b30282dcaed282133b9e06af` onto main `96ee733`. CurrentAgent remains V0.10. No new strategy, rule, or scoring value is promoted.

## Delivered

- Offline Python 3.14 x64 Windows installer with dependencies, 139 approved development templates, source/template SHA256 manifest, and per-install evidence directory.
- Manual structural shanten and minimum-shanten discard candidates. Experimental Runtime Vision display remains explicitly unpromoted and preserves individual state gates; incomplete public state cannot unlock visible remainder/danger capabilities.
- Evidence-backed live observation page with explicit unknowns, bounded 1000-row display and append-only session JSONL. Suggestions never establish actual actions or settlement evidence.
- Separate plain-Chinese assistance window; technical diagnostics remain accessible separately. Manual-score and evidence-marker buttons removed from the main interface at user request; recording/evidence APIs remain.
- Guarded launcher prevents spawn children from reopening UI. Tesseract runs with CREATE_NO_WINDOW on Windows. Timeline paths use POSIX separators, including old-session import.

## Validation and limits

Packaged-runtime checks passed: child-process message exchange, environment Doctor, source/template hashes, classifier template loading, Demo/manual UI, timeline page, standalone assistant, manual discard sample, UNKNOWN abstention and synthetic OCR digits `1000`. Final repository regression is recorded in the sync PR; earlier iterations passed 640/641/646 tests at their respective revisions.

Latest local installer: `HuianMahjong_Test_0.2.0_shanten-20261004-192914_Setup.exe`, 94,324,224 bytes. SHA256: `0bb7e97169d79cd5f667536cfc76acf807458b50a6b5c62ca57563ee2ad957f3`. Generated binaries, private recordings and temporary screenshots are not committed.

User reports actual local/video-window recognition almost entirely unavailable and slow response. Diagnostic screenshot reports score/hand/remaining unreadable, trusted hand count 0, Gold unknown, and M2 template missing. These are failure/abstention observations, not a measured accuracy rate. Full game frames and per-stage timing have not yet been analyzed. Player-window scale/borders and CPU performance are hypotheses, not established causes. Template/category coverage is a known gate, but it does not alone explain missing geometry.

Template loading/classifier rebuilding per burst and repeated CLI OCR are visible potential overheads; their timing is not yet measured. No cache optimization or accuracy fix is claimed. Formal source-disjoint validation remains #7's unchanged frozen promotion contract. Full V0.10 legal-action advisory and direct video-file testing are not connected. Executor remains off.

## Resource-cache follow-up (2026-10-06)

Runtime now caches the template resource bundle by resolved dataset path and
session (bounded to 16 entries). Repeated bursts reuse the classifier; a changed
session rebuilds its own source-excluded bank. Installed templates are assumed
immutable during a session; restart the process after updating template files.
Identity threshold 0.82, source exclusion, UNKNOWN and Executor gates are unchanged.

Measured on Linux/Python 3.12 with this branch's actual template bank: three cold
resource builds took 103.670 / 75.626 / 74.412 ms; three cache hits took
0.001 / 0.001 / <0.001 ms. These are resource-loading measurements only, not
Windows/video end-to-end latency or an accuracy claim. Tests exercise repeated
bursts and changed-session exclusion. The previously delivered EXE has not been
rebuilt and does not contain this fix.

Branch comparison with #117 at `38ed6b8` confirms the package branch also lacks
the development M2 template and direct-video runner. This cache fix does not
resolve those gaps or missing geometry/Gold identity. Do not claim the branches
or installed binary are synchronized.
