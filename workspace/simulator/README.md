# Simulator V0.1

`Simulator.run()` retains the historical READY-only safe stop.

`Simulator.run_opening(seed, dice_total)` deterministically replays the currently
implemented Huian opening: shuffled 144-tile wall, dealer/idle dealing,
dealer-first flower replacement and opening-gold planning. It returns a frozen,
replayable `SimulationResult` at `OPENING_QIANGJIN_CHECK` until the complete
抢金 declaration, priority and settlement rules are confirmed.

No action is selected or inferred after that stop. The result includes its seed,
dice total, event trace, state hash, phase, wall count and unresolved rule IDs.