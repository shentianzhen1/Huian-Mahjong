from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from huian.rules import DEFAULT_RULE_SNAPSHOT
from huian.version import PROJECT_VERSION
from workspace.ai import CURRENT_AGENT_NAME, CURRENT_AGENT_VERSION
from workspace.hint_alpha.doctor import (
    DoctorCheck, _runtime_geometry_schema_check, collect_doctor_report,
)


ALL_MODULES = {
    "tkinter",
    "PIL",
    "numpy",
    "cv2",
    "windows_capture",
    "win32gui",
    "win32process",
    "win32ui",
}


class HintAlphaDoctorTests(unittest.TestCase):
    def collect(self, root, *, modules=ALL_MODULES, system="Windows", tesseract="C:/Tesseract/tesseract.exe", installed=PROJECT_VERSION):
        with (
            patch(
                "workspace.hint_alpha.doctor._module_available",
                side_effect=lambda name: name in modules,
            ),
            patch("workspace.hint_alpha.doctor.platform.system", return_value=system),
            patch("workspace.hint_alpha.doctor.shutil.which", return_value=tesseract),
            patch("workspace.hint_alpha.doctor.metadata.version", return_value=installed),
            patch(
                "workspace.hint_alpha.doctor._runtime_geometry_schema_check",
                return_value=DoctorCheck(
                    "runtime.geometry_component_schema", "PASS",
                    "fixture geometry schema", "runtime_vision",
                ),
            ),
        ):
            return collect_doctor_report(root)

    def test_ready_windows_environment_reports_provenance_and_executor_off(self):
        with TemporaryDirectory() as temp:
            report = self.collect(temp)

        self.assertTrue(report.demo_ready)
        self.assertTrue(report.live_capture_ready)
        self.assertTrue(report.public_state_ocr_ready)
        self.assertFalse(report.executor_enabled)
        self.assertEqual(report.project_version, PROJECT_VERSION)
        self.assertEqual(report.rule_snapshot_id, DEFAULT_RULE_SNAPSHOT.fingerprint)
        self.assertEqual(report.agent_name, CURRENT_AGENT_NAME)
        self.assertEqual(report.agent_version, CURRENT_AGENT_VERSION)
        self.assertTrue(all(item.status == "PASS" for item in report.checks))

    def test_missing_tesseract_keeps_capture_ready_but_marks_ocr_unavailable(self):
        with TemporaryDirectory() as temp:
            report = self.collect(temp, tesseract=None)

        self.assertTrue(report.demo_ready)
        self.assertTrue(report.live_capture_ready)
        self.assertFalse(report.public_state_ocr_ready)
        check = next(item for item in report.checks if item.check_id == "ocr.tesseract")
        self.assertEqual(check.status, "WARN")

    def test_missing_windows_capture_dependency_fails_live_only(self):
        modules = ALL_MODULES - {"windows_capture"}
        with TemporaryDirectory() as temp:
            report = self.collect(temp, modules=modules)

        self.assertTrue(report.demo_ready)
        self.assertFalse(report.live_capture_ready)
        check = next(
            item for item in report.checks
            if item.check_id == "module.windows_capture"
        )
        self.assertEqual(check.status, "FAIL")

    def test_non_windows_environment_can_be_demo_ready_not_live_ready(self):
        modules = {"tkinter", "PIL", "numpy", "cv2"}
        with TemporaryDirectory() as temp:
            report = self.collect(
                temp,
                modules=modules,
                system="Linux",
                tesseract="/usr/bin/tesseract",
            )

        self.assertTrue(report.demo_ready)
        self.assertFalse(report.live_capture_ready)
        self.assertTrue(report.public_state_ocr_ready)
        platform_check = next(
            item for item in report.checks
            if item.check_id == "platform.windows"
        )
        self.assertEqual(platform_check.status, "WARN")

    def test_package_version_mismatch_fails_demo_readiness(self):
        with TemporaryDirectory() as temp:
            report = self.collect(temp, installed="0.1.0")

        self.assertFalse(report.demo_ready)
        self.assertFalse(report.live_capture_ready)
        check = next(
            item for item in report.checks
            if item.check_id == "package.version"
        )
        self.assertEqual(check.status, "FAIL")

    def test_evidence_directory_is_created_and_writable(self):
        with TemporaryDirectory() as temp:
            target = Path(temp) / "nested" / "evidence"
            report = self.collect(target)
            self.assertTrue(target.is_dir())
            check = next(
                item for item in report.checks
                if item.check_id == "evidence.write"
            )
            self.assertEqual(check.status, "PASS")

    def test_geometry_schema_checks_actual_class_contract(self):
        module_name = "workspace.vision.tiles_runtime_v0_2.dynamic_geometry"
        for component, expected in (
            (type("CompleteGeometry", (), {"gold_skin": None}), "PASS"),
            (type("OldGeometry", (), {}), "FAIL"),
        ):
            with self.subTest(expected=expected), patch.dict(
                sys.modules, {module_name: SimpleNamespace(GeometryComponent=component)},
            ):
                check = _runtime_geometry_schema_check()
                self.assertEqual(check.status, expected)
                self.assertEqual(check.capability, "runtime_vision")

    def test_unavailable_geometry_import_fails_diagnostic(self):
        with patch.dict(
            sys.modules,
            {"workspace.vision.tiles_runtime_v0_2.dynamic_geometry": None},
        ):
            check = _runtime_geometry_schema_check()
        self.assertEqual(check.status, "FAIL")
        self.assertIn("cannot import Runtime geometry", check.detail)


if __name__ == "__main__":
    unittest.main()
