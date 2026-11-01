# Windows test installer upgrade behavior — 2026-10-13

Issue #45 packaging fix: previous installers created a fresh timestamped program
directory and an additional timestamped desktop shortcut on each installation.
Native Unicode shell-link APIs replace WScript shortcut saves, which failed
with Chinese link names on the English Windows CI runner.
Shortcut/process ownership comparisons normalize existing Windows long/8.3
paths, including legacy shortcut targets whose parent still exists.

New installations use `%LOCALAPPDATA%\HuianMahjongTest\current` and update the
single desktop entry `惠安麻将测试版-向听辅助.lnk`. Records live outside the
replaceable program in `%LOCALAPPDATA%\HuianMahjongTest\data\hint_alpha`.
Earlier installers without the layout marker retain their original launch data
path; the new marker selects shared data even during staged self-check.

## Upgrade transaction

1. Lock the installer root and refuse upgrades while an identified old program
   process is running. Never terminate the game, app or its capture workers.
2. Extract into a temporary sibling directory, verify payload hashes and run
   the bundled launcher's doctor before touching the working program.
3. Preserve recognized legacy installation data byte-for-byte under
   `data\legacy\<old-directory>`. Conflicting archive files stop the upgrade
   rather than overwriting evidence. Shared current data remain in place.
4. Move the previous current program aside, promote the checked stage and
   replace the fixed shortcut. Restore the previous program if activation or
   shortcut creation fails before commit.
5. Remove identified old program directories and redundant old shortcuts only
   after promotion/data preservation. Unrecognized folders/shortcuts are left
   alone. Locked cleanup remnants are retained and listed in the completion UI.

Legacy cleanup recognizes the old version/timestamp name plus build metadata,
launcher and Python files. Reparse points in managed program/data trees stop
the upgrade; cleanup does not traverse linked user directories. Concurrent
installation attempts cannot both replace the same program.

Downloaded `*_Setup.exe` files are separate user downloads and are not deleted.
The new installer can clean recognized installed legacy versions; continuing
to run an old Setup EXE still uses its old accumulation behavior. The new
installer's data archive contains retained records, not additional program
versions. Private video/evidence are never uploaded by this process.

## Validation boundary

Local Python tests verify the installed launch data path, spawn import behavior,
dependency lock and payload/entrypoint contracts. The Windows workflow runs the
actual compiled EXE with `--install-test` in a temporary root and temporary
desktop, exercising legacy-data migration, fixed entry, repeated installation,
conflicting data, failed new doctor, running-app refusal and preservation of an
unrelated folder. Test mode changes root/UI only; it uses the production upgrade
transaction and doctor. No user's actual desktop or install is touched by CI.

Windows compilation/upgrade verification must pass on the new HEAD before
claiming a verified replacement installer. This packaging fix changes no
Runtime threshold, classifier, AI V0.10, Rules or Executor behavior.
