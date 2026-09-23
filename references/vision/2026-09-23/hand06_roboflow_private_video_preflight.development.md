# Issue #69 — sixth-hand private video: Roboflow source preflight

This document records a **completed local preflight, not cloud inference or an accuracy result**. The corresponding original recording and extracted frame pixels remain outside the public GitHub checkout.

- Source session: `match_evidence_001_hand_06`; original **match** group: `match_evidence_001`. This is the same original match as hands 1 and 2, **not an independent source-disjoint holdout**.
- Original source SHA256: `d50f6722982adb0fdfe3ad8e0b9d1f4155defcfbefebd77e8f10cbc4d3b19a78`.
- Decoded source: H.264, **1046 × 480**, **2736** frames, approximately **29 fps**, **94.36 seconds**.
- Twelve video-relative sample frames, with both early and late public-river states: `250, 400, 550, 700, 850, 1000, 1150, 1300, 1500, 1750, 2000, 2250`.
- Local source-hash check **passed** before decoding. The source-locked private probe exported **12/12 private JPEG frames** plus a private sanitized preflight JSON. The sampled frames include in-app replay control overlays, animations, exposed melds, and a partly covered river; this is a *diagnostic convenience sample*, not a blinded annotation set.
- Mode `preflight_no_api`; external upload **false**; model calls **0**; model detections **0** because no model was called; approved face ground truth **0** in this selected-frame package; recognition accuracy **not evaluated**. Do not present `0 detections` as a model failure.
- Network access from the local container failed to resolve Roboflow's service domain. The GitHub Actions public screenshot benchmark is independent of these private frames and must not claim to have evaluated this recording.
- The original recording, screenshots, private Drive reference and user API credential are **not committed**. GitHub-hosted testing of the private sixth-hand frames requires a separate explicitly authorized *private* binary handoff. Do not expose a private Drive access URL or a temporary bearer download link in public workflow source or logs.

Reproduce on a private machine with the matching source file and the already-committed source-locked probe:

```bash
python -m workspace.vision.roboflow_video_probe \
  --video /private/hand06.mp4 \
  --expected-sha256 d50f6722982adb0fdfe3ad8e0b9d1f4155defcfbefebd77e8f10cbc4d3b19a78 \
  --source-group match_evidence_001 \
  --frames 250,400,550,700,850,1000,1150,1300,1500,1750,2000,2250 \
  --output /private/hand06_roboflow_preflight.json
```

To attempt actual Roboflow inference from a private execution environment, explicitly add `--cloud` with your secret in the `ROBOFLOW_API_KEY` environment variable, and verify that outbound network/model access is available. Any future face-level accuracy denominator must come from separately adjudicated frame-specific labels, not predictions or confidence scores. Executor remains OFF.
