# Simulator V0.1

`Simulator.run()` retains the historical READY-only safe stop.

`Simulator.run_normal_hand()` is an isolated simulation-only profile. It skips
the unresolved Qiangjin check and disables special Hu branches. It uses ordinary
draw/discard/claim/Hu transitions only. Pinghu is settled as +1/-1 and Zimo as
+2/-2 strictly to prove replayability and zero-sum accounting; these are not
the final Huian scoring formula.

`benchmark_normal_hands(count=100)` is manual. Default tests run a 20-hand
smoke batch, each with a max_steps guard; UNKNOWN exits are recorded in
SimulationResult.unresolved and never retried indefinitely.

`Simulator.run_opening(seed, dice_total)` deterministically replays the currently
implemented Huian opening: shuffled 144-tile wall, dealer/idle dealing,
dealer-first flower replacement and opening-gold planning. It returns a frozen,
replayable `SimulationResult` at `OPENING_QIANGJIN_CHECK` until the complete
抢金 declaration, priority and settlement rules are confirmed.

No action is selected or inferred after that stop. The result includes its seed,
dice total, event trace, state hash, phase, wall count and unresolved rule IDs.
