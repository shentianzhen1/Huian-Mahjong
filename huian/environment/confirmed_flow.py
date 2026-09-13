"""Compatibility names; confirmed flow now lives in the default environment."""
from huian.rules.adapter import HuianRulesAdapter
from .engine import HuianEnvironment


class HuianConfirmedFlowAdapter(HuianRulesAdapter):
    """Compatibility adapter using shared legality and validation."""


class HuianConfirmedFlowEnvironment(HuianEnvironment):
    """Compatibility environment using shared atomic transitions."""
