from pathlib import Path
import ast
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HintAlphaLiveEntrypointTests(unittest.TestCase):
    def test_source_launcher_uses_stateful_live_app(self):
        launcher = (ROOT / "START_HINT_ALPHA.bat").read_text(encoding="utf-8")

        self.assertIn("-m workspace.hint_alpha.live_app", launcher)
        self.assertNotIn("-m workspace.hint_alpha.app\n", launcher)

    def test_packaged_launcher_uses_stateful_live_app(self):
        launcher = (ROOT / "packaging" / "launch.py").read_text(encoding="utf-8")

        self.assertIn("doctor, live_app", launcher)
        self.assertIn("live_app.main()", launcher)
        self.assertNotIn("\n    app.main()", launcher)

    def test_windows_ci_executes_installed_live_ui_smoke(self):
        workflow = (
            ROOT / ".github" / "workflows" / "test-installer.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("packaging/smoke_test_installed.py $payload", workflow)
        self.assertIn("live UI smoke", workflow)

    def test_live_wiring_resets_on_confirmed_hand_boundary_and_binds_runtime(self):
        path = ROOT / "workspace" / "hint_alpha" / "live_app.py"
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))

        self.assertIn("confirmed_public_hand_boundary", source)
        self.assertIn("self.runtime_advice_pipeline.reset()", source)
        self.assertIn("with self.runtime_advice_pipeline.bind()", source)
        self.assertIn("regressions/jumps fail closed", source)
        self.assertIn("Executor remains\nOFF", source)
        self.assertNotIn("workspace.simulator", source)
        self.assertNotIn("dice_total", source)
        self.assertNotIn("wall_index", source)
        self.assertNotIn("random_seed", source)


if __name__ == "__main__":
    unittest.main()
