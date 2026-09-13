"""Load bundled legacy packages without modifying sys.path or copying their code."""
import importlib.util
from pathlib import Path
import sys


def load_package(name, directory):
    path = Path(__file__).resolve().parents[1] / "legacy_code" / directory
    if name in sys.modules:
        module = sys.modules[name]
        if Path(module.__file__).resolve() != (path / "__init__.py").resolve():
            raise ImportError(f"{name} already refers to a different package")
        return module
    spec = importlib.util.spec_from_file_location(
        name, path / "__init__.py", submodule_search_locations=[str(path)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


core = load_package("qzcore", "core_v0.1.1/qzcore")
env = load_package("qzenv", "environment_v0.1/qzenv")
