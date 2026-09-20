# Rule Isolation and Change Protocol

This project must remain safe when a Mahjong rule is later corrected.

The design goal is **small blast radius**:

> A corrected rule should replace one registered rule value / service and its
> focused tests. It must not silently contaminate Simulator results, AI
> promotion evidence, Vision, or unrelated state transitions.

## 1. Two layers of truth

- `RULE_STATUS.md` / `RULE_EVIDENCE_MATRIX.md` remain the human evidence truth.
- `huian/rules/registry.py` is the runtime-facing, versioned mirror for
  high-impact rules.

The registry is not allowed to invent a rule. Evidence changes first; runtime
metadata follows.

## 2. Every high-impact rule has a stable ID

A `RuleRecord` contains:

- stable `rule_id`
- domain: physical / legality / state machine / fan / scoring / settlement / match
- evidence status: CONFIRMED / HIGH_CONFIDENCE / WORKING / UNKNOWN
- independent revision number
- current JSON-safe value
- blast-radius level: low / medium / high / critical
- anonymized evidence IDs
- implementation boundary
- explicit dependencies

Do not encode unrelated facts into one giant rule record.

Example:

- `legality.rob_kong_scope`
- `settlement.rob_kong_multiplier`
- `settlement.rob_kong_full`

This means a later payment-rule correction does not require rewriting the
already-confirmed added-kong legality.

## 3. Immutable RuleSnapshot

`DEFAULT_RULE_SNAPSHOT` is immutable and has a deterministic SHA-256
fingerprint.

Changing any registered rule status, revision, value, dependency, evidence
reference, or impact metadata changes the fingerprint.

Research alternatives use a separate snapshot via `with_overrides()`; they
never mutate the default snapshot.

Production code currently reads the default snapshot. Do not claim a research
override changed gameplay unless the relevant runtime service explicitly
accepts that alternate snapshot.

## 4. Evaluation contamination barrier

Saved Simulator evaluations write the full rule-snapshot manifest into
`run.json`.

Paired eight-hand AI reports include:

- `rule_snapshot_id`
- `rule_snapshot_label`

A replay rejects a different rule fingerprint.

Therefore an AI result created under an older rule snapshot is historical
evidence, not automatic promotion evidence for the new snapshot.

### Promotion rule

When a **HIGH/CRITICAL** rule used by score or legality changes:

1. increment that rule's revision;
2. update the registry value/status/evidence;
3. update fixture + focused regression;
4. let the snapshot fingerprint change;
5. rerun the relevant baseline under the new snapshot;
6. compare the candidate and CurrentAgent under the **same fingerprint**.

Never merge win-rate/EV numbers across different rule fingerprints.

Vision-only measurements are not invalidated by a scoring-rule change unless
the changed rule affects the observed public-state interpretation.

## 5. CONFIRMED gate

Code that needs a real target-room value should use
`DEFAULT_RULE_SNAPSHOT.require_confirmed(rule_id)`.

- CONFIRMED -> value may enter official score/EV.
- WORKING -> research/project fallback only.
- UNKNOWN -> stop / UNKNOWN path.
- HIGH_CONFIDENCE -> must not silently become official terminal scoring.

This is especially important for:

- Gang-Hu
- Rob-Kong full settlement
- Qiangjin settlement
- Sanjindao full settlement
- real Eight-Flower terminal settlement

## 6. Small-module migration rule

Do not rewrite Rules/Environment wholesale.

Migrate high-impact constants gradually:

1. register the existing behavior;
2. add a consistency test proving registry == current runtime;
3. switch only that module to read the registry;
4. run full regression;
5. move to the next rule.

Current migrated examples include dealer-base values, Youjin/Double/Triple
multipliers, Sanjindao multiplier, Rob-Kong multiplier, Eight-Flower working
values, and the Youjin response-discard contract.

## 7. Required process for a corrected rule

For any new correction:

1. **Evidence**
   - add anonymized evidence reference;
   - mark old evidence/interpretation superseded where needed.
2. **Human truth**
   - update `RULE_STATUS.md`;
   - update `RULE_EVIDENCE_MATRIX.md`.
3. **Runtime record**
   - update one or more existing stable rule IDs;
   - increment only the changed rule revision;
   - do not rename the ID just because the value changed.
4. **Focused fixture/test**
   - reproduce the real case;
   - add negative/boundary tests where relevant.
5. **Implementation**
   - change the narrow legality/state/scoring service only.
6. **Blast-radius check**
   - run dependent regression;
   - run invariants: tile conservation, legal actions, zero-sum settlement,
     no UNKNOWN-as-draw/win, deterministic replay.
7. **AI evidence**
   - old score/EV reports remain archived under their old fingerprint;
   - rerun only the affected AI evaluation chain.

## 8. What must remain independent

A scoring correction must not automatically change:

- tile legality;
- draw source;
- wall accounting;
- Vision classification;
- Executor coordinates.

A legality correction must not silently rewrite:

- fan aggregation;
- settlement formula;
- match score bookkeeping.

A Vision correction must not alter Mahjong rules.

These boundaries are the main defense against one mistaken rule damaging the
whole project.
