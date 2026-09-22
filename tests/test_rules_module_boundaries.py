import unittest

from huian.rules.engine import (
    HuDecomposition as EngineHuDecomposition,
    HuResult as EngineHuResult,
    KongFanResult as EngineKongFanResult,
    Settlement as EngineSettlement,
    YoujinMeldDecomposition as EngineYoujinMeldDecomposition,
    YoujinMeldResult as EngineYoujinMeldResult,
    YoujinScoreTerms as EngineYoujinScoreTerms,
    nonnegative_int as engine_nonnegative_int,
)
from huian.rules.models import (
    HuDecomposition,
    HuResult,
    KongFanResult,
    Settlement,
    YoujinMeldDecomposition,
    YoujinMeldResult,
    YoujinScoreTerms,
)
from huian.rules.values import nonnegative_int


class RulesModuleBoundaryTests(unittest.TestCase):
    def test_engine_keeps_existing_model_exports(self):
        self.assertIs(EngineSettlement, Settlement)
        self.assertIs(EngineHuDecomposition, HuDecomposition)
        self.assertIs(EngineHuResult, HuResult)
        self.assertIs(EngineYoujinMeldDecomposition, YoujinMeldDecomposition)
        self.assertIs(EngineYoujinMeldResult, YoujinMeldResult)
        self.assertIs(EngineKongFanResult, KongFanResult)
        self.assertIs(EngineYoujinScoreTerms, YoujinScoreTerms)

    def test_engine_keeps_nonnegative_int_export(self):
        self.assertIs(engine_nonnegative_int, nonnegative_int)
        engine_nonnegative_int(0, "value")
        with self.assertRaises(ValueError):
            engine_nonnegative_int(-1, "value")
        with self.assertRaises(ValueError):
            engine_nonnegative_int(True, "value")


if __name__ == "__main__":
    unittest.main()
