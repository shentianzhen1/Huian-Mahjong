"""Environment doctor for the internal Hint Alpha build.

The doctor diagnoses installation/runtime readiness without enabling any game
automation. Tesseract is optional for capture/evidence and is reported
separately as PublicState OCR readiness.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from importlib import metadata, util
import json
from pathlib import Path
import platform
import shutil
import sys
from typing import Iterable

from huian.rules import DEFAULT_RULE_SNAPSHOT
from huian.version import PROJECT_NAME, PROJECT_VERSION
from workspace.ai import CURRENT_AGENT_NAME, CURRENT_AGENT_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "hint_alpha"


@dataclass(frozen=True)
class DoctorCheck:
    check_id: str
    status: str
    detail: str
    capability: str

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass(frozen=True)
class DoctorReport:
    project_version: str
    python: str
    executable: str
    platform: str
    rule_snapshot_id: str
    agent_name: str
    agent_version: str
    executor_enabled: bool
    demo_ready: bool
    live_capture_ready: bool
    public_state_ocr_ready: bool
    checks: tuple[DoctorCheck, ...]

    def to_dict(self):
        return {
            **asdict(self),
            "checks": [asdict(item) for item in self.checks],
        }


def _module_available(name: str) -> bool:
    try:
        return util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _module_check(name: str, *, capability: str, required: bool) -> DoctorCheck:
    available = _module_available(name)
    if available:
        return DoctorCheck(
            f"module.{name}", "PASS", f"{name} available", capability
        )
    return DoctorCheck(
        f"module.{name}",
        "FAIL" if required else "WARN",
        f"{name} not available",
        capability,
    )


def _writable_check(path: Path) -> DoctorCheck:
    probe = path / ".hint_alpha_doctor_write_test"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return DoctorCheck(
            "evidence.write",
            "FAIL",
            f"cannot write evidence directory {path}: {type(exc).__name__}: {exc}",
            "demo",
        )
    return DoctorCheck(
        "evidence.write",
        "PASS",
        f"evidence directory writable: {path}",
        "demo",
    )


def _package_check() -> DoctorCheck:
    try:
        installed = metadata.version(PROJECT_NAME)
    except metadata.PackageNotFoundError:
        return DoctorCheck(
            "package.version",
            "FAIL",
            f"{PROJECT_NAME} is not installed in this Python environment",
            "demo",
        )
    if installed != PROJECT_VERSION:
        return DoctorCheck(
            "package.version",
            "FAIL",
            f"installed package {installed} != runtime {PROJECT_VERSION}",
            "demo",
        )
    return DoctorCheck(
        "package.version",
        "PASS",
        f"{PROJECT_NAME} {installed}",
        "demo",
    )


def collect_doctor_report(output_root: str | Path | None = None) -> DoctorReport:
    output = Path(output_root) if output_root is not None else DEFAULT_OUTPUT
    checks: list[DoctorCheck] = []

    supported_python = (3, 10) <= sys.version_info[:2] < (3, 15)
    checks.append(DoctorCheck(
        "python.version",
        "PASS" if supported_python else "FAIL",
        f"Python {platform.python_version()} at {sys.executable}",
        "demo",
    ))
    checks.append(_package_check())

    for module in ("tkinter", "PIL", "numpy", "cv2"):
        checks.append(_module_check(module, capability="demo", required=True))

    checks.append(_writable_check(output))

    is_windows = platform.system() == "Windows"
    checks.append(DoctorCheck(
        "platform.windows",
        "PASS" if is_windows else "WARN",
        f"platform={platform.system()}; live capture requires Windows",
        "live_capture",
    ))
    for module in ("windows_capture", "win32gui", "win32process", "win32ui"):
        checks.append(_module_check(
            module,
            capability="live_capture",
            required=is_windows,
        ))

    tesseract = shutil.which("tesseract")
    checks.append(DoctorCheck(
        "ocr.tesseract",
        "PASS" if tesseract else "WARN",
        f"tesseract={tesseract}" if tesseract
        else "Tesseract not found on PATH; capture/evidence still work",
        "public_state_ocr",
    ))

    demo_ready = all(
        item.status == "PASS"
        for item in checks
        if item.capability == "demo"
    )
    live_capture_ready = (
        demo_ready
        and is_windows
        and all(
            item.status == "PASS"
            for item in checks
            if item.capability == "live_capture"
        )
    )
    public_state_ocr_ready = demo_ready and bool(tesseract)

    return DoctorReport(
        project_version=PROJECT_VERSION,
        python=platform.python_version(),
        executable=sys.executable,
        platform=platform.system(),
        rule_snapshot_id=DEFAULT_RULE_SNAPSHOT.fingerprint,
        agent_name=CURRENT_AGENT_NAME,
        agent_version=CURRENT_AGENT_VERSION,
        executor_enabled=False,
        demo_ready=demo_ready,
        live_capture_ready=live_capture_ready,
        public_state_ocr_ready=public_state_ocr_ready,
        checks=tuple(checks),
    )


def _human_lines(report: DoctorReport) -> Iterable[str]:
    yield f"Hint Alpha Doctor / project {report.project_version}"
    yield (
        f"Agent {report.agent_name} {report.agent_version} | "
        f"Rules {report.rule_snapshot_id[:12]} | Executor OFF"
    )
    yield ""
    for item in report.checks:
        yield f"[{item.status}] {item.check_id}: {item.detail}"
    yield ""
    yield f"Demo Ready: {'YES' if report.demo_ready else 'NO'}"
    yield f"Live Capture Ready: {'YES' if report.live_capture_ready else 'NO'}"
    yield (
        "PublicState OCR Ready: "
        + ("YES" if report.public_state_ocr_ready else "NO")
    )
    if not report.public_state_ocr_ready:
        yield "NOTE: OCR unavailable does not disable capture or evidence recording."
    yield "Executor: OFF"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check Hint Alpha local readiness")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output-root")
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="return failure unless Windows live capture dependencies are ready",
    )
    args = parser.parse_args(argv)

    report = collect_doctor_report(args.output_root)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("\n".join(_human_lines(report)))

    ready = report.live_capture_ready if args.require_live else report.demo_ready
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
