# Exact-frame re-review checkpoint — 2026-10-13

Successor to `new_recording_frame_identity_20261013.md`. This checkpoint is
revealed development evidence only; no classifier evaluation or promotion is
claimed.

The current Drive folder inventory contains eight MOV segments. This replaces
the earlier two-file availability count, not the original-match grouping:
files and folder names do not prove independent matches. Only the previously
registered 66,372,077-byte segment was downloaded and verified in this run.

Source SHA256:
`98dfe5a05a7148eaa018e1ba8f0cb44f688bf51f87f93185a26894a89706e3e7`.

Sequential decoding from ordinal zero produced 2796×1290 RGB frames:

| Ordinal | Raw RGB SHA256 |
| --- | --- |
| 693 | `9a620ef582769fac920714383d2dac47e37d2be8d6d3bf3bf455ee51cde9d2ed` |
| 1734 | `867f728d633bbcb899a630320dbd77bd3c1e64fa812d2e6a435d096fbbb7de18` |
| 2774 | `83aaf397f255457c6fd9e55096172e500c2e0e9db5a50d2ec1d2e3e5c9756c64` |

Ordinal 2774 matches the previously committed sequential-decoding audit exactly.
All three full-frame views were actually inspected in this run. Ordinal 1734
shows a large PENG animation and an elevated concealed tile; do not mark this
checkpoint stable merely because identities can be visually read. Five-frame
hand/animation consistency is not yet verified at any of these checkpoints.
The truth lists remain unlocked and accuracy metrics remain invalid. Preserve
the preselected animation checkpoint as a rejection/recovery diagnostic rather
than silently moving it to a cleaner frame to improve reported accuracy.

Local validation after installing Vision dependencies:
`python -m unittest discover -s tests -p '*whole_hand_baseline*' -v`:
six tests passed, zero skips. This includes sequential ordinal access and
reviewed RGB hash mismatch rejection. Decoder used OpenCV 5.0.0; no inference
was run and no production dependency pin was changed.

Next: inspect the five exact ordinal frames around each centre, lock only
supported hand labels/counts and explicitly record animation/unstable inputs,
then review automatic geometry before scoring the frozen candidate. Private
video/frame/crop bytes remain outside GitHub. Original-match independence is
still UNVERIFIED. Runtime threshold 0.82, V0.10, read-only Hint, Executor OFF
and Draft/unmerged PR #126 remain unchanged.
