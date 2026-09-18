"""Rule-neutral simulator scaffolding."""
from .core import RandomAgent, SimulationResult, Simulator, SimulatorConfig, make_wall
from .evaluation import BatchEvaluation, HandSummary, run_many_normal_hands
from .match import MatchProgressState, MatchScoreState, score_eight_hand_match
from .match_runner import (MatchHandContext, MatchHandRecord, MatchHandResult,
                           MatchRunResult, MatchRunner, run_eight_hand_match,
                           run_real_ordinary_match)
from .unknowns import summarize_match_rule_gaps

__all__ = ["RandomAgent", "SimulationResult", "Simulator", "SimulatorConfig", "make_wall",
           "BatchEvaluation", "HandSummary", "run_many_normal_hands",
           "MatchProgressState", "MatchScoreState", "score_eight_hand_match",
           "MatchHandContext", "MatchHandRecord", "MatchHandResult",
           "MatchRunResult", "MatchRunner", "run_eight_hand_match",
           "run_real_ordinary_match", "summarize_match_rule_gaps"]
