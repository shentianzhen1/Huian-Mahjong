# Roboflow mahjong v83: GitHub screenshot benchmark and private video probe

Development-only comparison for the public model `mahjong-baq4s/83`, not a
production Vision detector or a source-disjoint blind holdout.

## What GitHub can honestly run

The repository already contains **9 public game screenshots with 17 approved,
partial, standard-tile face annotations** spanning two already-reviewed source
sessions. `workspace.vision.roboflow_public_eval` checks each source image's
stored SHA256 **before uploading anything**. It maps `1C..9C` to `M1..M9`,
`1D..9D` to `P1..P9`, `1B..9B` to `S1..S9`; wind/dragon labels use
`EW SW WW NW RD GD WD`. `1S..4S` and `1F..4F` intentionally stay
UNKNOWN: they do **not** have proven Huian class mappings.

The GitHub Actions workflow `Roboflow Public Trial` runs source-hash checks,
pure offline tests and a synthetic-video smoke test on PRs **without a key**.
On trusted `main` only, it can call Roboflow on the 9 **already-public**
screenshots if the `ROBOFLOW_API_KEY` GitHub Actions repository secret exists.
A manual `workflow_dispatch` with `run_cloud=true` is also available.
Every cloud attempt is bounded to at most 12 approved public images, with 9
currently eligible. The code uses Roboflow's official `inference-sdk`,
header-based authentication and the published model ID.

The sanitized `roboflow-public-screenshot-trial` Actions artifact includes
only aggregate counts, not the key, pictures or raw model responses. An absent
secret produces an explicit SKIPPED cloud step, not an invented accuracy result.
A failed cloud request fails its CI step with a sanitized error type, never
printing an SDK error body that might contain credential/request data.

Example offline check from a repository checkout:

```bash
python -m pip install -e ".[vision]"
python -m unittest discover -s tests -p "test_roboflow_*.py" -v
python -m workspace.vision.roboflow_public_eval --root . \
  --output /tmp/roboflow_public_offline.json
```

For an explicitly authorized online call on an existing public dataset:

```bash
python -m pip install "inference-sdk>=1.5,<2"
# ROBOFLOW_API_KEY is supplied via your private environment, NEVER in a file.
python -m workspace.vision.roboflow_public_eval --root . --cloud \
  --output /tmp/roboflow_public_cloud.json
```

## What the resulting numbers actually mean

The public screenshots were only **partially annotated**. At IoU >= 0.5 we
measure exact correct tile, mismatched/unsupported tile with an overlapping
face, and missing boxes for those 17 reviewed faces. We can report approved-box
tile recall and classification accuracy *conditional on a matched box*. We
**cannot report overall detection precision, full-frame mAP or a blind target
app recognition rate** because non-annotated tiles may be legitimate detections
and both source sessions have been used in development. The training-source
overlap of this third-party Roboflow model is not independently established.

## Private full-video input stays outside public GitHub

`workspace.vision.roboflow_video_probe` accepts a real source video,
its exact SHA256, a **match-level** source group and explicit video-relative
frame indices. The source hash is checked before decoding or cloud inference.
It returns source image digests, frame indices, full-frame normalized candidate
boxes and an UNKNOWN-safe report. Without reviewed face boxes for the sampled
video frames, it reports NO recognition accuracy. Its optional `--cloud`
uploads only chosen JPEG frames; optional private frame exports and reports
**must stay outside the public repository**.

Previously inspected *development* video examples (the two hands belong to the
same match; the special replay was already examined):

```bash
python -m workspace.vision.roboflow_video_probe \
  --video /private/3.mp4 \
  --expected-sha256 1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3 \
  --source-group match_evidence_001 --frames 406,492,590,688 \
  --output /tmp/hand1_roboflow_preflight.json

# Cloud mode adds --cloud and reads ROBOFLOW_API_KEY from the environment.
```

Second-hand source variant `4.mp4` SHA256:
`1597ef429288ad50ce26340fcda580c17c735cf3875845c4c309db5652853b22`;
frames `301,494,693,990`; **same original match group**. A different
previously reviewed replay can be used for development, not a blind holdout.

**The private MP4s are not in this public GitHub repository.** GitHub Actions
cannot automatically access the user's unshared Drive recordings. Do not add
video URLs, API keys, raw frames or personalized cloud responses to this repo.
To conduct GitHub-hosted full-video cloud inference later, arrange a
private, explicitly authorized temporary source handoff. Until then, the
Actions experiment uses the already-public screenshots, while the SHA-locked
real-video CLI is available in a private execution environment.

No changes to Rules, Simulator, Environment, production Vision, Hint or
Executor. `safe_for_executor=false` is invariant in both reports.
