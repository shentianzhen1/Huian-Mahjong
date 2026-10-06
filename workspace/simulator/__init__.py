"""Rule-neutral simulator scaffolding."""
from .core import RandomAgent, SimulationResult, Simulator, SimulatorConfig, make_wall
from .staged_opening import run_random_staged_opening, run_staged_opening
from .target_hand import run_target_hand
from .evaluation import BatchEvaluation, HandSummary, run_many_normal_hands
from .match import MatchProgressState, MatchScoreState, score_eight_hand_match
from .match_runner import (MatchHandContext, MatchHandRecord, MatchHandResult,
                           MatchRunResult, MatchRunner, run_eight_hand_match,
                           run_real_ordinary_match, run_real_youjin_match,
                           run_target_room_match)
from .match_evaluation import (MatchAttemptSummary, PairedMatchEvaluation,
                               run_paired_real_matches)
from .unknowns import summarize_match_rule_gaps
from .kong_audit import KongAuditRecorder, KongAuditSummary

__all__ = ["RandomAgent", "SimulationResult", "Simulator", "SimulatorConfig", "make_wall",
           "run_staged_opening", "run_random_staged_opening", "run_target_hand",
           "BatchEvaluation", "HandSummary", "run_many_normal_hands",
           "MatchProgressState", "MatchScoreState", "score_eight_hand_match",
           "MatchHandContext", "MatchHandRecord", "MatchHandResult",
           "MatchRunResult", "MatchRunner", "run_eight_hand_match",
           "run_real_ordinary_match", "run_real_youjin_match", "run_target_room_match",
           "MatchAttemptSummary",
           "PairedMatchEvaluation", "run_paired_real_matches",
           "summarize_match_rule_gaps", "CalibratingShantenAgent",
           "DealInCalibrationBin", "DealInCalibrationRecorder",
           "DealInCalibrationReport", "DealInCalibrationSample",
           "run_ordinary_deal_in_calibration",
           "summarize_deal_in_calibration",
           "CalibratingTenpaiRiskShantenAgent", "TenpaiRiskBin",
           "TenpaiRiskCalibrationRecorder", "TenpaiRiskCalibrationReport",
           "TenpaiRiskCalibrationSample", "run_tenpai_risk_calibration",
           "summarize_tenpai_risk_calibration", "TenpaiStateCalibrationSample",
           "TenpaiStateRecorder", "PublicTenpaiProbabilityModel",
           "TenpaiProbabilityBin", "TenpaiProbabilityCell",
           "TenpaiStateCalibrationReport", "collect_tenpai_state_samples",
           "fit_public_tenpai_probability_model",
           "evaluate_public_tenpai_probability_model",
           "run_public_tenpai_probability_calibration"]
__all__.extend(["KongAuditRecorder", "KongAuditSummary"])

from .opponent_calibration import (CalibratingShantenAgent,
                                   CalibratingTenpaiRiskShantenAgent,
                                   DealInCalibrationBin, DealInCalibrationRecorder,
                                   DealInCalibrationReport, DealInCalibrationSample,
                                   TenpaiRiskBin, TenpaiRiskCalibrationRecorder,
                                   TenpaiRiskCalibrationReport,
                                   TenpaiRiskCalibrationSample,
                                   TenpaiStateCalibrationSample, TenpaiStateRecorder,
                                   PublicTenpaiProbabilityModel,
                                   TenpaiProbabilityBin, TenpaiProbabilityCell,
                                   TenpaiStateCalibrationReport,
                                   collect_tenpai_state_samples,
                                   fit_public_tenpai_probability_model,
                                   evaluate_public_tenpai_probability_model,
                                   run_public_tenpai_probability_calibration,
                                   run_ordinary_deal_in_calibration,
                                   run_tenpai_risk_calibration,
                                   summarize_deal_in_calibration,
                                   summarize_tenpai_risk_calibration)
