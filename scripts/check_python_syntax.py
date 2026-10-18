"""Check tracked active Python sources without importing project dependencies."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import subprocess
import tokenize


ACTIVE_ROOTS = {"huian", "mahjong_framework", "workspace", "tests", "scripts"}


def check_file(path: Path) -> str | None:
    try:
        with tokenize.open(path) as stream:
            source = stream.read()
        ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeError, OSError) as error:
        line = getattr(error, "lineno", None)
        return f"{path}:{line or 0}: {error}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="Explicit files; defaults to tracked active Python sources")
    args = parser.parse_args()
    if args.files:
        paths = [Path(value) for value in args.files]
    else:
        root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
        names = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"]).decode().split("\0")
        paths = [root / name for name in names if name.endswith(".py") and (len(Path(name).parts) == 1 or Path(name).parts[0] in ACTIVE_ROOTS)]
    errors = [error for path in paths if (error := check_file(path))]
    for error in errors:
        print(error)
    print(f"Python syntax: checked {len(paths)} files; errors={len(errors)}")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
