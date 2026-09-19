"""Load the legacy compatibility packages in source and installed layouts."""
import importlib
import importlib.util
from pathlib import Path
import sys


def _source_tree_path(directory):
    return Path(__file__).resolve().parents[1] / "legacy_code" / directory


def load_package(name, directory):
    """Load a bundled compatibility package without mutating sys.path.

    Wheels install qzcore/qzenv as normal private compatibility packages.
    A source checkout keeps the historical legacy_code layout, so development
    runs can still fall back to loading that exact tree in place.
    """
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name != name:
            raise

    path = _source_tree_path(directory)
    init_file = path / "__init__.py"
    if not init_file.exists():
        raise ImportError(
            f"Compatibility package {name!r} is unavailable; expected installed "
            f"package or source tree at {init_file}"
        )

    if name in sys.modules:
        module = sys.modules[name]
        if Path(module.__file__).resolve() != init_file.resolve():
            raise ImportError(f"{name} already refers to a different package")
        return module

    spec = importlib.util.spec_from_file_location(
        name, init_file, submodule_search_locations=[str(path)]
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
