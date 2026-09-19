# Archived one-off GitHub Actions workflows

Archived: 2026-09-19.

These workflows were one-time AI calibration / pilot / confirmation jobs. They are
kept here for reproducibility but are intentionally no longer active under
`.github/workflows/`.

Use `.github/workflows/ai-paired-eval.yml` for new routine fixed-wall,
seat-swapped, identity-stable-RNG comparisons. Historical conclusions belong in
`references/ai/` and current promotion rules belong in Issue #6 / AGENTS.md.

## one-shanten-v09-confirm-once.yml

Original blob: `7e6ee2ca38ea1df9f4de9fdebc3a4443e39861a2`

```yaml
name: OneShanten V09 Independent Confirm

on:
  push:
    paths:
      - ".github/workflows/one-shanten-v09-confirm-once.yml"

jobs:
  validate:
    strategy:
      fail-fast: false
      matrix:
        include:
          - { block: seeds_96000_96004, start: 96000, stop: 96005 }
          - { block: seeds_96005_96009, start: 96005, stop: 96010 }
          - { block: seeds_96010_96014, start: 96010, stop: 96015 }
          - { block: seeds_96015_96019, start: 96015, stop: 96020 }
          - { block: seeds_96020_96024, start: 96020, stop: 96025 }
          - { block: seeds_98000_98004, start: 98000, stop: 98005 }
          - { block: seeds_98005_98009, start: 98005, stop: 98010 }
          - { block: seeds_98010_98014, start: 98010, stop: 98015 }
          - { block: seeds_98015_98019, start: 98015, stop: 98020 }
          - { block: seeds_98020_98024, start: 98020, stop: 98025 }
          - { block: seeds_100000_100004, start: 100000, stop: 100005 }
          - { block: seeds_100005_100009, start: 100005, stop: 100010 }
          - { block: seeds_100010_100014, start: 100010, stop: 100015 }
          - { block: seeds_100015_100019, start: 100015, stop: 100020 }
          - { block: seeds_100020_100024, start: 100020, stop: 100025 }
          - { block: seeds_102000_102004, start: 102000, stop: 102005 }
          - { block: seeds_102005_102009, start: 102005, stop: 102010 }
          - { block: seeds_102010_102014, start: 102010, stop: 102015 }
          - { block: seeds_102015_102019, start: 102015, stop: 102020 }
          - { block: seeds_102020_102024, start: 102020, stop: 102025 }
    runs-on: ubuntu-latest
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run independent V0.9 confirmation
        env:
          BLOCK: ${{ matrix.block }}
          START: ${{ matrix.start }}
          STOP: ${{ matrix.stop }}
        run: |
          python -B - <<'PY'
          import json, os
          from time import perf_counter
          from workspace.ai import OneShantenTwoPlyRiskAgent, TenpaiRiskTieBreakAgent
          from workspace.simulator import run_paired_real_matches

          def v09(seed=None):
              return OneShantenTwoPlyRiskAgent(seed=seed, template_samples=32)

          def v06(seed=None):
              return TenpaiRiskTieBreakAgent(seed=seed, template_samples=32)

          start = int(os.environ["START"])
          stop = int(os.environ["STOP"])
          started = perf_counter()
          report = run_paired_real_matches(
              range(start, stop),
              agent_factories=(v09, v06),
              agent_names=("OneShantenV09", "CurrentV06"),
              max_steps=1000,
              initial_dealer=0,
          )
          payload = report.to_dict()
          payload.pop("per_match", None)
          payload["block"] = os.environ["BLOCK"]
          payload["elapsed_seconds"] = perf_counter() - started
          print("V09_CONFIRM_START")
          print(json.dumps(payload, ensure_ascii=False, indent=2))
          print("V09_CONFIRM_END")
          PY
```

## one-shanten-v09-pilot-once.yml

Original blob: `2136ce3bb1a2112fe2c49d680035e67c7ca7aef7`

```yaml
name: OneShanten TwoPly V09 Pilot

on:
  push:
    paths:
      - ".github/workflows/one-shanten-v09-pilot-once.yml"

jobs:
  validate:
    strategy:
      fail-fast: false
      matrix:
        include:
          - { block: seeds_88000_88004, start: 88000, stop: 88005 }
          - { block: seeds_88005_88009, start: 88005, stop: 88010 }
          - { block: seeds_88010_88014, start: 88010, stop: 88015 }
          - { block: seeds_88015_88019, start: 88015, stop: 88020 }
          - { block: seeds_88020_88024, start: 88020, stop: 88025 }
          - { block: seeds_90000_90004, start: 90000, stop: 90005 }
          - { block: seeds_90005_90009, start: 90005, stop: 90010 }
          - { block: seeds_90010_90014, start: 90010, stop: 90015 }
          - { block: seeds_90015_90019, start: 90015, stop: 90020 }
          - { block: seeds_90020_90024, start: 90020, stop: 90025 }
          - { block: seeds_92000_92004, start: 92000, stop: 92005 }
          - { block: seeds_92005_92009, start: 92005, stop: 92010 }
          - { block: seeds_92010_92014, start: 92010, stop: 92015 }
          - { block: seeds_92015_92019, start: 92015, stop: 92020 }
          - { block: seeds_92020_92024, start: 92020, stop: 92025 }
          - { block: seeds_94000_94004, start: 94000, stop: 94005 }
          - { block: seeds_94005_94009, start: 94005, stop: 94010 }
          - { block: seeds_94010_94014, start: 94010, stop: 94015 }
          - { block: seeds_94015_94019, start: 94015, stop: 94020 }
          - { block: seeds_94020_94024, start: 94020, stop: 94025 }
    runs-on: ubuntu-latest
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run V0.9 versus CurrentAgent V0.6
        env:
          BLOCK: ${{ matrix.block }}
          START: ${{ matrix.start }}
          STOP: ${{ matrix.stop }}
        run: |
          python -B - <<'PY'
          import json, os
          from time import perf_counter
          from workspace.ai import OneShantenTwoPlyRiskAgent, TenpaiRiskTieBreakAgent
          from workspace.simulator import run_paired_real_matches

          def v09(seed=None):
              return OneShantenTwoPlyRiskAgent(seed=seed, template_samples=32)

          def v06(seed=None):
              return TenpaiRiskTieBreakAgent(seed=seed, template_samples=32)

          start = int(os.environ["START"])
          stop = int(os.environ["STOP"])
          started = perf_counter()
          report = run_paired_real_matches(
              range(start, stop),
              agent_factories=(v09, v06),
              agent_names=("OneShantenV09", "CurrentV06"),
              max_steps=1000,
              initial_dealer=0,
          )
          payload = report.to_dict()
          payload.pop("per_match", None)
          payload["block"] = os.environ["BLOCK"]
          payload["elapsed_seconds"] = perf_counter() - started
          print("V09_PILOT_START")
          print(json.dumps(payload, ensure_ascii=False, indent=2))
          print("V09_PILOT_END")
          PY
```

## public-tenpai-calibration-once.yml

Original blob: `374ffbe33d4a6c0fa92082bbb962420a8458e309`

```yaml
name: Public Tenpai Probability Calibration

on:
  push:
    paths:
      - ".github/workflows/public-tenpai-calibration-once.yml"

jobs:
  calibrate:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Fit and validate public opponent-tenpai probability
        run: |
          python -B - <<'PY'
          import json
          from workspace.simulator import run_public_tenpai_probability_calibration

          model, report = run_public_tenpai_probability_calibration(
              range(130000, 130100),
              range(140000, 140100),
              max_steps=1000,
              wall_bucket_size=16,
              prior_strength=8.0,
              min_cell_count=30,
          )
          payload = report.to_dict()
          payload["model"] = {
              "wall_bucket_size": model.wall_bucket_size,
              "prior_strength": model.prior_strength,
              "min_cell_count": model.min_cell_count,
              "global_probability": model.global_probability,
          }
          print("TENPAI_CAL_START")
          print(json.dumps(payload, ensure_ascii=False, indent=2))
          print("TENPAI_CAL_END")
          PY
```

## public-tenpai-final-calibration-once.yml

Original blob: `69aab159fa2f4412d10b210fe6c4fd241b7ca52c`

```yaml
name: Public Tenpai Probability Final Calibration

on:
  push:
    paths:
      - ".github/workflows/public-tenpai-final-calibration-once.yml"

jobs:
  calibrate:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Train validate and final-test public tenpai model
        run: |
          python -B - <<'PY'
          import json
          from workspace.simulator import (
              collect_tenpai_state_samples,
              evaluate_public_tenpai_probability_model,
              fit_public_tenpai_probability_model,
          )

          train, train_status = collect_tenpai_state_samples(range(150000, 150150))
          valid, valid_status = collect_tenpai_state_samples(range(151000, 151100))
          test, test_status = collect_tenpai_state_samples(range(152000, 152150))

          candidates = []
          for bucket in (8, 12, 16, 24):
              for prior in (8.0, 24.0, 64.0):
                  model = fit_public_tenpai_probability_model(
                      train, wall_bucket_size=bucket,
                      prior_strength=prior, min_cell_count=30)
                  report = evaluate_public_tenpai_probability_model(
                      model, valid,
                      train_hands_attempted=150, test_hands_attempted=100,
                      train_status_counts=train_status,
                      test_status_counts=valid_status)
                  candidates.append({
                      "bucket": bucket,
                      "prior": prior,
                      "brier": report.brier_score,
                      "base_brier": report.constant_train_rate_brier,
                      "auc": report.auc,
                      "mean_prediction": report.mean_prediction,
                      "test_prevalence": report.test_prevalence,
                  })

          chosen = min(candidates, key=lambda x: (x["brier"], -(x["auc"] or 0.0)))
          model = fit_public_tenpai_probability_model(
              train, wall_bucket_size=chosen["bucket"],
              prior_strength=chosen["prior"], min_cell_count=30)
          final = evaluate_public_tenpai_probability_model(
              model, test,
              train_hands_attempted=150, test_hands_attempted=150,
              train_status_counts=train_status, test_status_counts=test_status)

          payload = {
              "train_samples": len(train),
              "validation_samples": len(valid),
              "final_test_samples": len(test),
              "train_status": train_status,
              "validation_status": valid_status,
              "final_test_status": test_status,
              "validation_candidates": candidates,
              "chosen": chosen,
              "final_test": final.to_dict(),
          }
          print("TENPAI_FINAL_START")
          print(json.dumps(payload, ensure_ascii=False, indent=2))
          print("TENPAI_FINAL_END")
          PY
```

## tenpai-loss-v07-pilot-once.yml

Original blob: `8b472a8f3369776573465ba3e129289a4880e679`

```yaml
name: TenpaiLoss V07 Pilot
# retry after synthetic-template scoring fallback

on:
  push:
    paths:
      - ".github/workflows/tenpai-loss-v07-pilot-once.yml"

jobs:
  validate:
    strategy:
      fail-fast: false
      matrix:
        include:
          - block: seeds_30000_30024
            start: 30000
            stop: 30025
          - block: seeds_32000_32024
            start: 32000
            stop: 32025
          - block: seeds_34000_34024
            start: 34000
            stop: 34025
          - block: seeds_36000_36024
            start: 36000
            stop: 36025
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run V0.7 versus CurrentAgent V0.6
        env:
          BLOCK: ${{ matrix.block }}
          START: ${{ matrix.start }}
          STOP: ${{ matrix.stop }}
        run: |
          python -B - <<'PY'
          import json, os
          from time import perf_counter
          from workspace.ai import TenpaiLossTieBreakAgent, TenpaiRiskTieBreakAgent
          from workspace.simulator import run_paired_real_matches

          def v07_factory(seed=None):
              return TenpaiLossTieBreakAgent(seed=seed, template_samples=32)

          def v06_factory(seed=None):
              return TenpaiRiskTieBreakAgent(seed=seed, template_samples=32)

          start = int(os.environ["START"])
          stop = int(os.environ["STOP"])
          started = perf_counter()
          report = run_paired_real_matches(
              range(start, stop),
              agent_factories=(v07_factory, v06_factory),
              agent_names=("TenpaiLossV07", "TenpaiRiskV06"),
              max_steps=1000,
              initial_dealer=0,
          )
          payload = report.to_dict()
          payload.pop("per_match", None)
          payload["block"] = os.environ["BLOCK"]
          payload["elapsed_seconds"] = perf_counter() - started
          print("V07_PILOT_START")
          print(json.dumps(payload, ensure_ascii=False, indent=2))
          print("V07_PILOT_END")
          PY
```

## tenpai-risk-64-vs-32-pilot-once.yml

Original blob: `227447a71766973e49b263fa4f95858768117bb0`

```yaml
name: TenpaiRisk 64vs32 Pilot

on:
  push:
    paths:
      - ".github/workflows/tenpai-risk-64-vs-32-pilot-once.yml"

jobs:
  validate:
    strategy:
      fail-fast: false
      matrix:
        include:
          - block: seeds_54000_54024
            start: 54000
            stop: 54025
          - block: seeds_56000_56024
            start: 56000
            stop: 56025
          - block: seeds_58000_58024
            start: 58000
            stop: 58025
          - block: seeds_60000_60024
            start: 60000
            stop: 60025
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Compare 64-template risk against CurrentAgent 32-template risk
        env:
          BLOCK: ${{ matrix.block }}
          START: ${{ matrix.start }}
          STOP: ${{ matrix.stop }}
        run: |
          python -B - <<'PY'
          import json, os
          from time import perf_counter
          from workspace.ai import TenpaiRiskTieBreakAgent
          from workspace.simulator import run_paired_real_matches

          def risk64(seed=None):
              return TenpaiRiskTieBreakAgent(seed=seed, template_samples=64)

          def risk32(seed=None):
              return TenpaiRiskTieBreakAgent(seed=seed, template_samples=32)

          start = int(os.environ["START"])
          stop = int(os.environ["STOP"])
          started = perf_counter()
          report = run_paired_real_matches(
              range(start, stop),
              agent_factories=(risk64, risk32),
              agent_names=("TenpaiRisk64", "CurrentV06_32"),
              max_steps=1000,
              initial_dealer=0,
          )
          payload = report.to_dict()
          payload.pop("per_match", None)
          payload["block"] = os.environ["BLOCK"]
          payload["elapsed_seconds"] = perf_counter() - started
          print("RISK64_PILOT_START")
          print(json.dumps(payload, ensure_ascii=False, indent=2))
          print("RISK64_PILOT_END")
          PY
```

## tenpai-risk-loss-v07b-confirm-once.yml

Original blob: `20d2b3da16c6477cfdd9f1958858c701b65b3e06`

```yaml
name: TenpaiRiskLoss V07b Confirm

on:
  push:
    paths:
      - ".github/workflows/tenpai-risk-loss-v07b-confirm-once.yml"

jobs:
  validate:
    strategy:
      fail-fast: false
      matrix:
        include:
          - block: seeds_46000_46024
            start: 46000
            stop: 46025
          - block: seeds_48000_48024
            start: 48000
            stop: 48025
          - block: seeds_50000_50024
            start: 50000
            stop: 50025
          - block: seeds_52000_52024
            start: 52000
            stop: 52025
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run V0.7b confirmation against CurrentAgent V0.6
        env:
          BLOCK: ${{ matrix.block }}
          START: ${{ matrix.start }}
          STOP: ${{ matrix.stop }}
        run: |
          python -B - <<'PY'
          import json, os
          from time import perf_counter
          from workspace.ai import TenpaiRiskLossTieBreakAgent, TenpaiRiskTieBreakAgent
          from workspace.simulator import run_paired_real_matches

          def v07b_factory(seed=None):
              return TenpaiRiskLossTieBreakAgent(seed=seed, template_samples=32)

          def v06_factory(seed=None):
              return TenpaiRiskTieBreakAgent(seed=seed, template_samples=32)

          start = int(os.environ["START"])
          stop = int(os.environ["STOP"])
          started = perf_counter()
          report = run_paired_real_matches(
              range(start, stop),
              agent_factories=(v07b_factory, v06_factory),
              agent_names=("TenpaiRiskLossV07b", "TenpaiRiskV06"),
              max_steps=1000,
              initial_dealer=0,
          )
          payload = report.to_dict()
          payload.pop("per_match", None)
          payload["block"] = os.environ["BLOCK"]
          payload["elapsed_seconds"] = perf_counter() - started
          print("V07B_CONFIRM_START")
          print(json.dumps(payload, ensure_ascii=False, indent=2))
          print("V07B_CONFIRM_END")
          PY
```

## tenpai-risk-loss-v07b-pilot-once.yml

Original blob: `5a1c4e8851033966928114d9cdea917149c2c293`

```yaml
name: TenpaiRiskLoss V07b Pilot

on:
  push:
    paths:
      - ".github/workflows/tenpai-risk-loss-v07b-pilot-once.yml"

jobs:
  validate:
    strategy:
      fail-fast: false
      matrix:
        include:
          - block: seeds_38000_38024
            start: 38000
            stop: 38025
          - block: seeds_40000_40024
            start: 40000
            stop: 40025
          - block: seeds_42000_42024
            start: 42000
            stop: 42025
          - block: seeds_44000_44024
            start: 44000
            stop: 44025
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run V0.7b versus CurrentAgent V0.6
        env:
          BLOCK: ${{ matrix.block }}
          START: ${{ matrix.start }}
          STOP: ${{ matrix.stop }}
        run: |
          python -B - <<'PY'
          import json, os
          from time import perf_counter
          from workspace.ai import TenpaiRiskLossTieBreakAgent, TenpaiRiskTieBreakAgent
          from workspace.simulator import run_paired_real_matches

          def v07b_factory(seed=None):
              return TenpaiRiskLossTieBreakAgent(seed=seed, template_samples=32)

          def v06_factory(seed=None):
              return TenpaiRiskTieBreakAgent(seed=seed, template_samples=32)

          start = int(os.environ["START"])
          stop = int(os.environ["STOP"])
          started = perf_counter()
          report = run_paired_real_matches(
              range(start, stop),
              agent_factories=(v07b_factory, v06_factory),
              agent_names=("TenpaiRiskLossV07b", "TenpaiRiskV06"),
              max_steps=1000,
              initial_dealer=0,
          )
          payload = report.to_dict()
          payload.pop("per_match", None)
          payload["block"] = os.environ["BLOCK"]
          payload["elapsed_seconds"] = perf_counter() - started
          print("V07B_PILOT_START")
          print(json.dumps(payload, ensure_ascii=False, indent=2))
          print("V07B_PILOT_END")
          PY
```

## two-ply-v08-confirm-once.yml

Original blob: `b65c0ddb1132e9ca12003fc66355cc01082862b4`

```yaml
name: TwoPly V08 Independent Confirm

on:
  push:
    paths:
      - ".github/workflows/two-ply-v08-confirm-once.yml"

jobs:
  validate:
    strategy:
      fail-fast: false
      matrix:
        include:
          - { block: seeds_70000_70004, start: 70000, stop: 70005 }
          - { block: seeds_70005_70009, start: 70005, stop: 70010 }
          - { block: seeds_70010_70014, start: 70010, stop: 70015 }
          - { block: seeds_70015_70019, start: 70015, stop: 70020 }
          - { block: seeds_70020_70024, start: 70020, stop: 70025 }
          - { block: seeds_72000_72004, start: 72000, stop: 72005 }
          - { block: seeds_72005_72009, start: 72005, stop: 72010 }
          - { block: seeds_72010_72014, start: 72010, stop: 72015 }
          - { block: seeds_72015_72019, start: 72015, stop: 72020 }
          - { block: seeds_72020_72024, start: 72020, stop: 72025 }
          - { block: seeds_74000_74004, start: 74000, stop: 74005 }
          - { block: seeds_74005_74009, start: 74005, stop: 74010 }
          - { block: seeds_74010_74014, start: 74010, stop: 74015 }
          - { block: seeds_74015_74019, start: 74015, stop: 74020 }
          - { block: seeds_74020_74024, start: 74020, stop: 74025 }
          - { block: seeds_76000_76004, start: 76000, stop: 76005 }
          - { block: seeds_76005_76009, start: 76005, stop: 76010 }
          - { block: seeds_76010_76014, start: 76010, stop: 76015 }
          - { block: seeds_76015_76019, start: 76015, stop: 76020 }
          - { block: seeds_76020_76024, start: 76020, stop: 76025 }
    runs-on: ubuntu-latest
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run independent V0.8 confirmation
        env:
          BLOCK: ${{ matrix.block }}
          START: ${{ matrix.start }}
          STOP: ${{ matrix.stop }}
        run: |
          python -B - <<'PY'
          import json, os
          from time import perf_counter
          from workspace.ai import TwoPlyShantenRiskAgent, TenpaiRiskTieBreakAgent
          from workspace.simulator import run_paired_real_matches

          def v08(seed=None):
              return TwoPlyShantenRiskAgent(seed=seed, template_samples=32)

          def v06(seed=None):
              return TenpaiRiskTieBreakAgent(seed=seed, template_samples=32)

          start = int(os.environ["START"])
          stop = int(os.environ["STOP"])
          started = perf_counter()
          report = run_paired_real_matches(
              range(start, stop),
              agent_factories=(v08, v06),
              agent_names=("TwoPlyV08", "CurrentV06"),
              max_steps=1000,
              initial_dealer=0,
          )
          payload = report.to_dict()
          payload.pop("per_match", None)
          payload["block"] = os.environ["BLOCK"]
          payload["elapsed_seconds"] = perf_counter() - started
          print("V08_CONFIRM_START")
          print(json.dumps(payload, ensure_ascii=False, indent=2))
          print("V08_CONFIRM_END")
          PY
```

## two-ply-v08-pilot-once.yml

Original blob: `bf3483516849424f6cee16c3e9372549767eecd2`

```yaml
name: TwoPly V08 Pilot

on:
  push:
    paths:
      - ".github/workflows/two-ply-v08-pilot-once.yml"

jobs:
  validate:
    strategy:
      fail-fast: false
      matrix:
        include:
          - block: seeds_62000_62024
            start: 62000
            stop: 62025
          - block: seeds_64000_64024
            start: 64000
            stop: 64025
          - block: seeds_66000_66024
            start: 66000
            stop: 66025
          - block: seeds_68000_68024
            start: 68000
            stop: 68025
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run V0.8 versus CurrentAgent V0.6
        env:
          BLOCK: ${{ matrix.block }}
          START: ${{ matrix.start }}
          STOP: ${{ matrix.stop }}
        run: |
          python -B - <<'PY'
          import json, os
          from time import perf_counter
          from workspace.ai import TwoPlyShantenRiskAgent, TenpaiRiskTieBreakAgent
          from workspace.simulator import run_paired_real_matches

          def v08(seed=None):
              return TwoPlyShantenRiskAgent(seed=seed, template_samples=32)

          def v06(seed=None):
              return TenpaiRiskTieBreakAgent(seed=seed, template_samples=32)

          start = int(os.environ["START"])
          stop = int(os.environ["STOP"])
          started = perf_counter()
          report = run_paired_real_matches(
              range(start, stop),
              agent_factories=(v08, v06),
              agent_names=("TwoPlyV08", "CurrentV06"),
              max_steps=1000,
              initial_dealer=0,
          )
          payload = report.to_dict()
          payload.pop("per_match", None)
          payload["block"] = os.environ["BLOCK"]
          payload["elapsed_seconds"] = perf_counter() - started
          print("V08_PILOT_START")
          print(json.dumps(payload, ensure_ascii=False, indent=2))
          print("V08_PILOT_END")
          PY
```

## two-ply-v08-retry-once.yml

Original blob: `abb84631c6dc260bdf788b74fc0d33bc1b7740a1`

```yaml
name: TwoPly V08 Retry Missing Blocks

on:
  push:
    paths:
      - ".github/workflows/two-ply-v08-retry-once.yml"

jobs:
  validate:
    strategy:
      fail-fast: false
      matrix:
        include:
          - { block: seeds_62000_62004, start: 62000, stop: 62005 }
          - { block: seeds_62005_62009, start: 62005, stop: 62010 }
          - { block: seeds_62010_62014, start: 62010, stop: 62015 }
          - { block: seeds_62015_62019, start: 62015, stop: 62020 }
          - { block: seeds_62020_62024, start: 62020, stop: 62025 }
          - { block: seeds_66000_66004, start: 66000, stop: 66005 }
          - { block: seeds_66005_66009, start: 66005, stop: 66010 }
          - { block: seeds_66010_66014, start: 66010, stop: 66015 }
          - { block: seeds_66015_66019, start: 66015, stop: 66020 }
          - { block: seeds_66020_66024, start: 66020, stop: 66025 }
          - { block: seeds_68000_68004, start: 68000, stop: 68005 }
          - { block: seeds_68005_68009, start: 68005, stop: 68010 }
          - { block: seeds_68010_68014, start: 68010, stop: 68015 }
          - { block: seeds_68015_68019, start: 68015, stop: 68020 }
          - { block: seeds_68020_68024, start: 68020, stop: 68025 }
    runs-on: ubuntu-latest
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Run missing V0.8 block
        env:
          BLOCK: ${{ matrix.block }}
          START: ${{ matrix.start }}
          STOP: ${{ matrix.stop }}
        run: |
          python -B - <<'PY'
          import json, os
          from time import perf_counter
          from workspace.ai import TwoPlyShantenRiskAgent, TenpaiRiskTieBreakAgent
          from workspace.simulator import run_paired_real_matches

          def v08(seed=None):
              return TwoPlyShantenRiskAgent(seed=seed, template_samples=32)

          def v06(seed=None):
              return TenpaiRiskTieBreakAgent(seed=seed, template_samples=32)

          start = int(os.environ["START"])
          stop = int(os.environ["STOP"])
          started = perf_counter()
          report = run_paired_real_matches(
              range(start, stop),
              agent_factories=(v08, v06),
              agent_names=("TwoPlyV08", "CurrentV06"),
              max_steps=1000,
              initial_dealer=0,
          )
          payload = report.to_dict()
          payload.pop("per_match", None)
          payload["block"] = os.environ["BLOCK"]
          payload["elapsed_seconds"] = perf_counter() - started
          print("V08_RETRY_START")
          print(json.dumps(payload, ensure_ascii=False, indent=2))
          print("V08_RETRY_END")
          PY
```

## v08-decision-diagnostics-once.yml

Original blob: `3caa0f5fa741bf968d474e420abc17bbe43baa5c`

```yaml
name: V08 Decision Diagnostics

on:
  push:
    paths:
      - ".github/workflows/v08-decision-diagnostics-once.yml"

jobs:
  diagnose:
    strategy:
      fail-fast: false
      matrix:
        include:
          - { block: diag_80000_80004, start: 80000, stop: 80005 }
          - { block: diag_82000_82004, start: 82000, stop: 82005 }
          - { block: diag_84000_84004, start: 84000, stop: 84005 }
          - { block: diag_86000_86004, start: 86000, stop: 86005 }
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Compare V0.8 shadow decisions on V0.6 trajectories
        env:
          BLOCK: ${{ matrix.block }}
          START: ${{ matrix.start }}
          STOP: ${{ matrix.stop }}
        run: |
          python -B - <<'PY'
          import json, os
          from collections import Counter
          from workspace.ai import (TenpaiRiskTieBreakAgent, TwoPlyShantenRiskAgent,
                                    best_offense_ties)
          from workspace.simulator import run_real_ordinary_match

          stats = Counter()
          by_shanten = Counter()
          changed_by_shanten = Counter()
          samples = []

          class DiagnosticAgent:
              def __init__(self, seed=None):
                  self.live = TenpaiRiskTieBreakAgent(seed=seed, template_samples=32)
                  self.shadow = TwoPlyShantenRiskAgent(seed=seed, template_samples=32)

              def choose_decision(self, observation, legal_actions):
                  live = self.live.choose_decision(observation, legal_actions)
                  shadow = self.shadow.choose_decision(observation, legal_actions)
                  stats["all_decisions"] += 1
                  if live.action != shadow.action:
                      stats["all_changed"] += 1

                  discards = [a for a in legal_actions if a.type.value == "DISCARD"]
                  if not discards:
                      return live
                  stats["discard_decisions"] += 1
                  legal_by_tile = {a.tile: a for a in discards}
                  ties = best_offense_ties(
                      observation.hand,
                      gold_tile=observation.gold_tile,
                      open_melds=len(observation.melds[observation.seat]),
                      visible_tiles=self.live._public_tiles(observation),
                      allowed_discards=tuple(legal_by_tile),
                  )
                  shanten = ties[0].shanten if ties else 99
                  by_shanten[str(shanten)] += 1
                  changed = live.action != shadow.action
                  if changed:
                      stats["discard_changed"] += 1
                      changed_by_shanten[str(shanten)] += 1

                  reason = shadow.reason
                  if len(ties) <= 1:
                      stats["no_exact_tie"] += 1
                  else:
                      stats["exact_tie"] += 1
                  if "exact offense tie includes gold" in reason:
                      stats["gold_guard"] += 1
                  elif "resolved by deterministic two-ply" in reason:
                      stats["two_ply_resolved"] += 1
                      if changed:
                          stats["changed_two_ply_resolved"] += 1
                  elif "two-ply offense still tied" in reason:
                      stats["two_ply_still_tied"] += 1
                      if changed:
                          stats["changed_after_risk"] += 1
                  elif "no exact offense tie" in reason:
                      stats["no_exact_tie_reason"] += 1
                  else:
                      stats["other_reason"] += 1

                  if changed and len(samples) < 24:
                      context = observation.match_context
                      samples.append({
                          "hand_index": None if context is None else context.hand_index,
                          "hands_remaining": None if context is None else context.hands_remaining,
                          "margin": None if context is None else context.margin_for(observation.seat),
                          "shanten": shanten,
                          "tie_count": len(ties),
                          "v06": getattr(live.action, "tile", None),
                          "v08": getattr(shadow.action, "tile", None),
                          "v08_reason": reason,
                      })
                  return live

          completed = 0
          stopped = Counter()
          for seed in range(int(os.environ["START"]), int(os.environ["STOP"])):
              result = run_real_ordinary_match(
                  seed=seed,
                  agent_factories=(DiagnosticAgent, DiagnosticAgent),
                  max_steps=1000,
                  initial_dealer=0,
              )
              if result.complete:
                  completed += 1
              else:
                  stopped[result.status] += 1

          out = {
              "block": os.environ["BLOCK"],
              "matches_requested": int(os.environ["STOP"]) - int(os.environ["START"]),
              "matches_completed": completed,
              "stopped": dict(stopped),
              "stats": dict(stats),
              "discard_by_shanten": dict(by_shanten),
              "changed_by_shanten": dict(changed_by_shanten),
              "changed_samples": samples,
          }
          print("V08_DIAG_START")
          print(json.dumps(out, ensure_ascii=False, indent=2))
          print("V08_DIAG_END")
          PY
```

## v09-one-shanten-cause-diagnostics-once.yml

Original blob: `d7000c06366e248381511772187ad04836eca0e3`

```yaml
name: V09 OneShanten Cause Diagnostics

on:
  push:
    paths:
      - ".github/workflows/v09-one-shanten-cause-diagnostics-once.yml"

jobs:
  diagnose:
    strategy:
      fail-fast: false
      matrix:
        include:
          - { block: diag_112000_112004, start: 112000, stop: 112005 }
          - { block: diag_114000_114004, start: 114000, stop: 114005 }
          - { block: diag_116000_116004, start: 116000, stop: 116005 }
          - { block: diag_118000_118004, start: 118000, stop: 118005 }
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Classify shanten-1 two-ply overrides on V0.6 trajectories
        env:
          BLOCK: ${{ matrix.block }}
          START: ${{ matrix.start }}
          STOP: ${{ matrix.stop }}
        run: |
          python -B - <<'PY'
          import json, os
          from collections import Counter
          from workspace.ai import (TenpaiRiskTieBreakAgent,
                                    analyze_two_ply_offense, best_offense_ties)
          from workspace.simulator import run_real_ordinary_match

          stats = Counter()
          cause_changed = Counter()
          cause_all = Counter()
          gap_sums = Counter()
          gap_max = Counter()
          samples = []

          def classify(estimates):
              pool = list(estimates)
              best = min(x.weighted_post_shanten for x in pool)
              pool2 = [x for x in pool if x.weighted_post_shanten == best]
              if len(pool2) == 1:
                  return "post_shanten", pool2
              best = max(x.terminal_win_copies for x in pool2)
              pool3 = [x for x in pool2 if x.terminal_win_copies == best]
              if len(pool3) == 1:
                  return "terminal_wins", pool3
              best = max(x.weighted_post_live_copies for x in pool3)
              pool4 = [x for x in pool3 if x.weighted_post_live_copies == best]
              if len(pool4) == 1:
                  return "post_live", pool4
              best = max(x.weighted_post_effective_types for x in pool4)
              pool5 = [x for x in pool4 if x.weighted_post_effective_types == best]
              if len(pool5) == 1:
                  return "post_types", pool5
              return "two_ply_tie", pool5

          class DiagnosticAgent:
              def __init__(self, seed=None):
                  self.live = TenpaiRiskTieBreakAgent(seed=seed, template_samples=32)

              def choose_decision(self, observation, legal_actions):
                  live = self.live.choose_decision(observation, legal_actions)
                  discards = [a for a in legal_actions if a.type.value == "DISCARD"]
                  if not discards:
                      return live
                  stats["discard_decisions"] += 1
                  legal_by_tile = {a.tile: a for a in discards}
                  public = self.live._public_tiles(observation)
                  ties = best_offense_ties(
                      observation.hand, gold_tile=observation.gold_tile,
                      open_melds=len(observation.melds[observation.seat]),
                      visible_tiles=public, allowed_discards=tuple(legal_by_tile))
                  if len(ties) <= 1 or ties[0].shanten != 1:
                      return live
                  stats["shanten1_exact_tie"] += 1
                  candidates = tuple(x.discard for x in ties)
                  if observation.gold_tile in candidates:
                      stats["gold_guard"] += 1
                      return live
                  estimates = analyze_two_ply_offense(
                      observation.hand, candidates,
                      gold_tile=observation.gold_tile,
                      open_melds=len(observation.melds[observation.seat]),
                      visible_tiles=public)
                  cause, finalists = classify(estimates)
                  cause_all[cause] += 1
                  if cause == "two_ply_tie":
                      return live
                  shadow_tile = finalists[0].discard
                  changed = shadow_tile != live.action.tile
                  if changed:
                      stats["changed"] += 1
                      cause_changed[cause] += 1

                  by = {x.discard:x for x in estimates}
                  v06 = by[live.action.tile]
                  shadow = by[shadow_tile]
                  if cause == "post_shanten":
                      gap = v06.weighted_post_shanten - shadow.weighted_post_shanten
                  elif cause == "terminal_wins":
                      gap = shadow.terminal_win_copies - v06.terminal_win_copies
                  elif cause == "post_live":
                      gap = shadow.weighted_post_live_copies - v06.weighted_post_live_copies
                  else:
                      gap = shadow.weighted_post_effective_types - v06.weighted_post_effective_types
                  if changed:
                      gap_sums[cause] += gap
                      gap_max[cause] = max(gap_max[cause], gap)
                      if len(samples) < 32:
                          ctx = observation.match_context
                          samples.append({
                              "cause": cause,
                              "gap": gap,
                              "v06": live.action.tile,
                              "shadow": shadow_tile,
                              "tie_count": len(ties),
                              "hand_index": None if ctx is None else ctx.hand_index,
                              "margin": None if ctx is None else ctx.margin_for(observation.seat),
                              "v06_metrics": {
                                  "post_s": v06.weighted_post_shanten,
                                  "wins": v06.terminal_win_copies,
                                  "live": v06.weighted_post_live_copies,
                                  "types": v06.weighted_post_effective_types,
                              },
                              "shadow_metrics": {
                                  "post_s": shadow.weighted_post_shanten,
                                  "wins": shadow.terminal_win_copies,
                                  "live": shadow.weighted_post_live_copies,
                                  "types": shadow.weighted_post_effective_types,
                              },
                          })
                  return live

          completed=0
          stopped=Counter()
          for seed in range(int(os.environ["START"]), int(os.environ["STOP"])):
              result=run_real_ordinary_match(
                  seed=seed, agent_factories=(DiagnosticAgent, DiagnosticAgent),
                  max_steps=1000, initial_dealer=0)
              if result.complete: completed += 1
              else: stopped[result.status] += 1

          out={
              "block":os.environ["BLOCK"],
              "matches_completed":completed,
              "stopped":dict(stopped),
              "stats":dict(stats),
              "cause_all":dict(cause_all),
              "cause_changed":dict(cause_changed),
              "gap_sums_changed":dict(gap_sums),
              "gap_max_changed":dict(gap_max),
              "samples":samples,
          }
          print("V09_CAUSE_START")
          print(json.dumps(out,ensure_ascii=False,indent=2))
          print("V09_CAUSE_END")
          PY
```

