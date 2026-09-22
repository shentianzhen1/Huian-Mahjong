from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

# Allowed cross-layer dependencies for the current umbrella distribution.
# Self-imports within a layer are always allowed.
ALLOWED = {
    "core": {"core"},
    "ai": {"core", "ai"},
    "vision": {"core", "vision"},
    "simulator": {"core", "ai", "simulator"},
    "hint_alpha": {"core", "ai", "vision", "hint_alpha"},
}


def layer_for_path(path: Path) -> str | None:
    relative = path.relative_to(ROOT)
    parts = relative.parts
    if not parts:
        return None
    if parts[0] in {"huian", "mahjong_framework"}:
        return "core"
    if len(parts) >= 2 and parts[0] == "workspace":
        if parts[1] in {"ai", "vision", "simulator", "hint_alpha"}:
            return parts[1]
    return None


def layer_for_import(module: str | None) -> str | None:
    if not module:
        return None
    if module == "huian" or module.startswith("huian."):
        return "core"
    if module == "mahjong_framework" or module.startswith("mahjong_framework."):
        return "core"
    if module == "workspace.ai" or module.startswith("workspace.ai."):
        return "ai"
    if module == "workspace.vision" or module.startswith("workspace.vision."):
        return "vision"
    if module == "workspace.simulator" or module.startswith("workspace.simulator."):
        return "simulator"
    if module == "workspace.hint_alpha" or module.startswith("workspace.hint_alpha."):
        return "hint_alpha"
    return None


def absolute_imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.lineno, node.module


class WorkspaceDependencyBoundaryTests(unittest.TestCase):
    def test_workspace_dependency_dag(self):
        violations = []
        roots = [
            ROOT / "huian",
            ROOT / "mahjong_framework",
            ROOT / "workspace" / "ai",
            ROOT / "workspace" / "vision",
            ROOT / "workspace" / "simulator",
            ROOT / "workspace" / "hint_alpha",
        ]
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*.py"):
                source_layer = layer_for_path(path)
                if source_layer is None:
                    continue
                for line, module in absolute_imports(path):
                    target_layer = layer_for_import(module)
                    if target_layer is None:
                        continue
                    if target_layer not in ALLOWED[source_layer]:
                        violations.append(
                            f"{path.relative_to(ROOT)}:{line}: "
                            f"{source_layer} -> {target_layer} via {module}"
                        )
        self.assertEqual(
            violations,
            [],
            "forbidden package dependency edges:\n" + "\n".join(violations),
        )

    def test_contract_has_no_reverse_product_edges(self):
        self.assertNotIn("simulator", ALLOWED["ai"])
        self.assertNotIn("ai", ALLOWED["vision"])
        self.assertNotIn("vision", ALLOWED["ai"])
        self.assertNotIn("simulator", ALLOWED["hint_alpha"])
        self.assertEqual(ALLOWED["core"], {"core"})


if __name__ == "__main__":
    unittest.main()
