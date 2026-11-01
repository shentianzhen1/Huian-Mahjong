"""Installed entry point; Windows spawn may import this file in a child."""
import multiprocessing
from pathlib import Path


def spawn_probe(output):
    output.put("spawn-ok")


def installed_data_root(root):
    layout = root / "INSTALL_LAYOUT"
    shared = layout.is_file() and layout.read_text().strip() == "shared-data-current-v1"
    return (root.parent if shared else root) / "data" / "hint_alpha"


def main():
    import os
    import sys

    root = Path(__file__).resolve().parent
    os.chdir(root)
    if "--spawn-check" in sys.argv:
        context = multiprocessing.get_context("spawn")
        output = context.Queue()
        process = context.Process(target=spawn_probe, args=(output,))
        process.start()
        try:
            assert output.get(timeout=15) == "spawn-ok"
            process.join(5)
            assert process.exitcode == 0
            print("SPAWN_OK")
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)
            output.close()
            output.join_thread()
        return
    from workspace.hint_alpha import app as shell_app, doctor, live_app
    shell_app.OUTPUT = installed_data_root(root)
    doctor.DEFAULT_OUTPUT = shell_app.OUTPUT
    if "--check" in sys.argv:
        sys.argv = [sys.argv[0], "--require-live"]
        raise SystemExit(doctor.main())
    if "--standard" in sys.argv:
        sys.argv.remove("--standard")
    elif "--experimental-runtime-advisory" not in sys.argv:
        sys.argv.append("--experimental-runtime-advisory")
    live_app.main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
