# Contributing

This project is evidence-driven. A clean implementation is not permission to
invent a Huian Mahjong rule.

## 小 PR / CI 分流

按 [开发与证据流程](docs/development_workflow.md) 将工作拆成可验收的切片：一个 Issue 对应一个具体问题；标明证据级别、UNKNOWN 边界及对应 CI。改动 `references/vision/**/*.json`、`references/rules/**/*.json`、`references/gameplay/**` 或 `tests/fixtures/**/*.json` 时，新增的 **Evidence Contracts** 工作流会单独校验文件哈希、开发标注来源、座位映射与结算 fixture，不把旧录像回归误报为独立盲测。新的独立来源以带版本 manifest 新增，保留已有锁定样本和真值。

## Before changing code

1. Read the relevant GitHub Issue / `TODO.md`.
2. For rule or settlement work, read the matching entry in `RULE_STATUS.md`
   and `RULE_EVIDENCE_MATRIX.md`.
3. Do not use an old `CHANGELOG.md` entry as current truth.
4. If evidence is incomplete, keep the result UNKNOWN / TODO / configurable.

## Evidence changes

When new gameplay evidence changes a rule:

1. preserve an anonymized evidence reference;
2. update `RULE_STATUS.md` and the evidence matrix;
3. add or update a fixture;
4. add a regression test;
5. only then change Rules / Environment / Settlement behavior.

Public fixtures must not contain real player display names or room identifiers.
Use neutral IDs such as `match_evidence_001`, `seat_0`, and `seat_1`.

## AI changes

- `CurrentAgent = MeldAwareShantenAgent V0.10`.
- V0.6 is the fixed main comparison baseline.
- V0.3 is the offense ablation baseline.
- A candidate must directly beat V0.10 under fixed wall + seat swap +
  identity-stable RNG before promotion.
- Use fresh seed ranges for confirmation.
- Never train on guessed UNKNOWN special-result multipliers.

For a cheap first gate, use the manual **AI Paired Evaluation** workflow with
25 fresh pairs before spending 100/200+ pairs.

## Vision changes

Do not report same-session temporal stability as cross-session accuracy.
Keep label audit human-reviewed: tools may flag a suspicious label but must not
rewrite ground truth automatically.

Vision uncertainty must remain advisory. `safe_for_executor=false` until the
full accuracy / temporal / PublicState / stress-test gates are explicitly met.

## Tests

Core:

```bash
python -B -m unittest discover -s tests -v
```

Vision:

```bash
python -m pip install -e ".[vision]"
python -B -m unittest workspace.vision.tiles_v0_1.test_tiles_v0_1 -v
```

Before merging package-layout changes, make sure the installed-package smoke test
passes; AI/Simulator imports must work outside the repository root.
