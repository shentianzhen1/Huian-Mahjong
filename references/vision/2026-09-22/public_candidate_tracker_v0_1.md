# Public Candidate Tracker V0.1

Date: 2026-09-22  
Issue: #69  
Status: development temporal geometry layer

## Goal

Turn per-frame Public Tile Detector geometry candidates into stable,
identity-free public tracks.

The tracker sits between:

    Public Tile Detector
      -> Public Candidate Tracker
      -> explicit CandidateChannel
      -> RiverSnapshot
      -> DiscardRiverObserver
      -> Temporal Action Assembler

It does not decide Mahjong semantics.

## Why this layer exists

The geometry detector is intentionally broad and may emit:

- true public tile faces;
- public meld groups;
- unrelated tile-like UI components;
- one-frame animation artifacts.

A single frame must never become a public action.

V0.1 therefore adds temporal stability before any channel is allowed to feed
RiverSnapshot.

## Track promotion

Default policy:

- candidate must match for 3 consecutive frames before APPEARED;
- a pending unconfirmed candidate is dropped after one missed frame;
- a confirmed candidate needs 2 consecutive misses before DISAPPEARED;
- maximum observation gap defaults to 0.5 s.

The 0.5 s value is a capture heuristic, not a Mahjong rule. Callers may tune it
for their capture cadence.

Geometry matching uses:

- same geometry_kind;
- scale-compatible width/height;
- local center movement;
- local overlap.

Absolute screen coordinates do not define track continuity.

## Capture continuity and stream epochs

Tracks never continue across source-session boundaries or an excessive capture
gap.

A session change records:

    session_changed_reset

A time gap larger than maximum_gap_seconds records:

    observation_gap_reset

Either reset clears active tracks, increments stream_epoch, and emits no false
DISAPPEARED event.

RiverSnapshot carries the same stream_epoch. DiscardRiverObserver and
MeldSnapshotObserver treat an epoch change as a hard continuity break: old
accepted/pending baselines are discarded and the new epoch must establish a
fresh stable baseline before any DISCARD/MELD_DELTA can be emitted.

This prevents sparse screenshots or capture stalls from turning two
non-contiguous states into a fabricated action.

## Geometry-kind boundary

A candidate that changes from for example:

    single_face -> upper_protrusion

does not silently inherit the old track ID.

This is fail-closed by design because a detector-shape change may represent a
new UI state rather than movement of the same public object.

## CandidateChannel

The tracker itself has no built-in river ROI.

To convert stable tracks into RiverSnapshot, a caller must explicitly define:

- channel name;
- accepted geometry kinds;
- optional reviewed normalized zones;
- minimum candidate-area overlap with those zones.

An empty zone list means all positions and is intended only when an upstream
component has already isolated the semantic channel.

This separation matters because the reviewed real frames already show at least
two opponent discard presentations:

- upper_protrusion large response tile;
- small upper single_face.

The tracker must not collapse those into one guessed fixed coordinate.

## RiverSnapshot bridge

river_snapshot_from_channel(...) converts only tracks accepted by an explicit
CandidateChannel.

Every emitted PublicTile currently has:

    tile_id = None

because Public Tile Detector V0.1 has no public-region identity model yet.

The resulting RiverSnapshot is therefore geometry-ready but identity-UNKNOWN.
It also carries stream_epoch so downstream observers cannot compare across
capture discontinuities.

## Real-frame regression

The Vision suite replays the same reviewed real JPG over three synthetic frame
IDs to verify that deterministic geometry survives the temporal gate:

- opponent P1 response tile -> stable upper_protrusion track;
- player P1 Peng group -> stable bottom_group track.

This proves detector -> tracker compatibility on real target-room pixels.

It does not claim replay-sequence precision/recall, because the source evidence
still consists of reviewed development frames rather than untouched continuous
video.

## Safety

- safe_for_hint=false
- safe_for_executor=false
- APPEARED means stable geometry track, not DISCARD;
- DISAPPEARED means stable geometry vanished, not CLAIM;
- no rule legality is consulted;
- no candidate becomes formal evidence automatically.

## Next slice

The next useful step is to define evidence-backed public channels from reviewed
continuous-frame sequences, then measure:

1. candidate-track false positives on non-target frames;
2. stable public-tile appearance precision/recall;
3. RiverSnapshot continuity;
4. downstream DiscardRiverObserver behavior;
5. eventual public tile identity coverage.

Do not connect Executor.
