# Issue #69 — Hand 1 representative closure

Status: **REPRESENTATIVE_CLOSURE_READY**

This document is a privacy-safe V0.1 closure checkpoint. It is not an exhaustive
zero-gap action ledger, a formal real-video accuracy claim, or Vision promotion
evidence. The latest structured private evidence and its correction overlay
supersede all earlier event-count drafts.

## Evidence-backed closure

| Stage | Representative evidence | Status |
|---|---|---|
| Opening | player perspective and dealer are established; opened Gold is M6; opening public-state sequence is reviewed | ready |
| Public actions | opponent P6 offer → player exposed kong; representative CHI sequences for both actors; stable river growth and exposed-meld deltas are available | ready |
| Dense river | both public rivers reach the observed terminal count; second-row and overlay cases are retained as fail-closed regression cases | ready |
| Youjin terminal | player draws P8, discards P5 and enters Youjin; opponent draws an unknown tile and discards M3; player draws P4, explicitly selects Youjin, and wins | ready |
| Settlement | player +68 and the observed settlement components are reconciled with the reviewed terminal state | ready |

The representative public-action set includes:

- one opponent offer consumed by a player exposed kong rather than entering the
  opponent discard river;
- an opponent CHI of S4-S5-S6;
- two separately observed opponent M8 discards;
- a player CHI of S3-S4-S5;
- an opponent CHI of S1-S2-S3;
- the final player P5 discard that enters Youjin;
- the opponent M3 discard before the player Youjin win.

## Non-blocking UNKNOWN facts

These facts remain explicitly unresolved and do not block the V0.1
representative closure:

- exact frame of the exposed-kong button selection;
- exact frame of the final P4 draw and Youjin selection;
- identity of the opponent's final drawn tile;
- exact timestamps for several user-confirmed intermediate events;
- any intermediate identity that lacks independent pixel evidence;
- full 144-tile conservation beyond the observed terminal/public subset.

No rule, prompt disappearance, animation, or expected turn order may fill these
gaps.

## Reconciliation boundary

Earlier drafts with different event totals are historical and must not be
combined. The closure uses the latest structured event snapshot plus explicit
correction overlay. The compact public-zone audit reconciles:

- player river: 19;
- opponent river: 19;
- player exposed meld tiles: 7;
- opponent exposed meld tiles: 6;
- observed terminal hand + meld counts: player 18, opponent 16.

These counts are observed-subset checks, not a claim that all 144 physical tiles
have been independently located.

## Exit decision

Hand 1 manual work exits at representative closure. Further frame-level work is
allowed only when it fixes a demonstrated replay failure or supplies one of the
scenario-coverage cases required for Hands 2–8.

Next work moves to the compact cross-hand scenario matrix and the eight-hand
automated replay harness. Executor remains OFF.
