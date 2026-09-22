# Hand Timeline V0.1

Hand Timeline turns a reviewed replay into two synchronized artifacts:

- `hand_XX_timeline.json` — canonical machine-readable evidence.
- `hand_XX_timeline.md` — deterministic human-readable review view.

The schema is implemented in `huian/evidence/timeline.py`.

## Evidence levels

- `direct_observation` — visible/readable in the source.
- `player_confirmed` — UI is incomplete/obscured but the player explicitly confirmed the meaning.
- `derived_from_confirmed` — deterministic consequence of already confirmed evidence.
- `unknown` — unresolved; never replace with a guessed value.

## Rules

1. Events must be timestamp-sorted.
2. Do not invent missing opening, action, or settlement details.
3. If total scores are recorded, they must conserve 2000.
4. UNKNOWN scoring / next-dealer / trigger predicates stay explicit.
5. Raw private replay video remains outside the public repository; store anonymous hashes and reviewed text evidence.
6. Timeline logs are evidence/debugging inputs only. They do not authorize Executor.

## Render

```powershell
python -m huian.evidence.timeline --input references/matches/<match_id>/hand_01_timeline.json --output references/matches/<match_id>/hand_01_timeline.md
```

The first real sample is:
`references/matches/match_evidence_002_double_you/hand_08_timeline.json`.
