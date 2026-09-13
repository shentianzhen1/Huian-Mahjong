"""Run with python -B -m huian.environment.demo from the repository root."""
from huian import HuianEnvironment, HuianGameState
from huian._legacy import env


def main():
    # A fully accounted mid-hand test fixture, not a simulated deal/opening.
    state = HuianGameState(
        phase="AFTER_DISCARD", gold_tile="P9", special_states=["NORMAL", "NORMAL"],
        pending_discard={"player": 1, "tile": "M3", "river_index": 0},
    )
    state.hands[0] = ["M1", "M2", "M4", "M5", "M7", "M8", "P1", "P2",
                      "P4", "S1", "S2", "S4", "E", "E", "E", "N"]
    state.discards[1] = ["M3"]
    remaining = env.full_wall()
    for tile in state.physical_tiles():
        remaining.remove(tile)
    for tile in remaining.copy():
        if tile in env.BASE_TILES and tile != "P9" and len(state.hands[1]) < 16:
            state.hands[1].append(tile)
            remaining.remove(tile)
    state.wall = remaining
    game = HuianEnvironment()
    game.set_state(state)
    report = game.action_report()
    print("Scenario only; unresolved alternatives:", report.unresolved)
    action = next(a for a in report.known_actions if a.type == env.ActionType.CHI)
    token = game.checkpoint()
    game.step(action)
    print("After Chi:", game.state.phase, "hand:", len(game.state.hands[0]),
          "opponent river:", game.state.discards[1])
    game.step(game.legal_actions()[0])
    print("After discard:", game.state.phase, "physical tiles:", len(game.state.physical_tiles()))
    print("Event count:", len(game.events))
    game.rollback(token)
    print("Rollback restored initial state:", game.state.state_hash() == state.state_hash())


if __name__ == "__main__":
    main()
