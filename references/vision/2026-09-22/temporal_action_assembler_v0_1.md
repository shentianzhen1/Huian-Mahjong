# Temporal Action Assembler V0.1

Date: 2026-09-22  
Issue: #69  
Status: read-only development reconstruction

## Purpose

Combine already-stable public observations into one auditable action stream.

The assembler receives:

- DISCARD
- HAND_DELTA
- MELD_DELTA
- direct public states such as GOLD / YOUJIN_STATE / HU / SETTLEMENT

and may emit:

- DISCARD
- CHI
- PENG
- MING_GANG
- ADD_KONG
- HU / SETTLEMENT / public state facts
- UNKNOWN_ACTION

It never asks the Rules engine whether the observed action is legal.

## Why a separate temporal layer

Low-level observers settle at different times:

- a river tile may stabilize first;
- hand count/identity may stabilize next;
- exposed meld geometry may stabilize last.

A single frame is therefore not enough to say "CHI".

The V0.1 assembler waits for the independent facts and calls the existing
fail-closed reconstructors only after the configured observer delay.

## Timing is not rule truth

AssemblyConfig requires two explicit capture/replay heuristics:

- claim_window_seconds
- assembly_delay_seconds

These values are **not Mahjong rules**.

The archived replay screenshots such as:

- 00:35 opponent P1 discard / response view
- 00:40 player P1 Peng visible
- 01:20 opponent S9 discard / response view
- 01:22 player S789 Chi visible

are sampled evidence frames from a replay recording. Their time differences do
not prove that the live client gives a five-second claim window.

Live capture and offline replay analysis may therefore use different calibrated
assembler timings without changing Rules or the event schema.

## Claimed meld assembly

For one MELD_DELTA, V0.1 searches unconsumed evidence in the configured time
window.

CHI / PENG / MING_GANG require a unique consistent combination of:

1. other actor DISCARD;
2. claimant HAND_DELTA;
3. claimant MELD_DELTA.

The semantic classification still comes from
reconstruct_claimed_meld(), which checks tile/count consistency.

If two evidence combinations are equally valid, the assembler emits UNKNOWN
with multiple_claim_evidence_combinations rather than choosing one.

## ADD_KONG

A MELD_DELTA carrying a reviewed previous_meld can be paired with a same-actor
HAND_DELTA through reconstruct_add_kong().

No public discard is required.

This matches the archived P1 sequence:

- opponent discard P1;
- player Peng P1;
- later fourth P1 visible in player concealed area;
- exposed P1 group changes to a stacked Kong.

The assembler does not infer the visual signature by itself; it only combines
facts produced by the observers.

## Evidence consumption

When a claim is reconstructed, the supporting:

- discard;
- hand delta;
- meld delta

are marked consumed for claim assembly.

The same discard cannot silently support a second later claim.

Direct DISCARD remains an emitted ledger event even when it is later consumed as
support for CHI/PENG/MING_GANG.

## Expiration and UNKNOWN

If a MELD_DELTA reaches the end of its configured claim window without one
unique reconstruction, it becomes:

    UNKNOWN_ACTION
    reason=meld_window_expired_without_unique_reconstruction

This is preferable to:

- guessing AN_GANG;
- attaching a stale discard;
- assuming the Rules engine explains the picture;
- silently dropping an unexplained public meld change.

## Ordering contract

Input RawObservation timestamps must be nondecreasing.

The capture/replay coordinator is responsible for ordering outputs from its
different observers before ingestion.

This gives deterministic replay and explicit evidence expiration.

## Current chain

    Runtime Vision / future public detector
       -> stable raw observations
       -> TemporalActionAssembler
       -> ReconstructedAction
       -> UNKNOWN-only Hand Timeline draft

Machine CORROBORATED remains reconstruction metadata. It does not automatically
become confirmed rule evidence.

## Non-goals

V0.1 does not:

- detect pixels;
- freeze public river ROIs;
- classify opponent hidden tiles;
- infer target-room claim legality;
- classify AN_GANG without a reviewed visual signature;
- promote machine output into RULE_STATUS;
- enable Executor.

## Next step

After this assembler is stable, Public Tile Detector calibration should focus on
feeding reliable DISCARD and opponent/public MELD snapshots into the already
working observer + assembler contracts.
