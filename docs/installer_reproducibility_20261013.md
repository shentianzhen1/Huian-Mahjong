# Windows test installer dependency contract — 2026-10-13

Scope: packaging reproducibility under Issue #45, not real capture acceptance
or Vision promotion. PR #126 remains Draft; Executor OFF, Agent V0.10 and
Runtime identity threshold 0.82 are unchanged.

## Verified input versions

These versions come from the successful Windows installer job `115184556555`
in run `38363969758` at `d49283323e8a8be479e7dbfcabbbf2a9551b5b8e`.

| Runtime input | Version |
| --- | --- |
| Python (Windows x64) | 3.14.7 |
| numpy | 2.5.4 |
| opencv-python | 5.0.0.93 |
| Pillow | 12.3.0 |
| pywin32 | 312 |
| windows-capture | 2.0.1 |

`packaging/constraints-windows-py314.txt` pins runtime dependencies. CI installs
`.[hint-alpha]` with this constraints file and pins the Python patch version.
The builder checks the selected interpreter and dependency environment before
copying a payload. Missing or different distributions stop the build.

The payload contains `DEPENDENCIES.txt`; `BUILD_INFO.json` records its SHA-256,
the Python version and actual pinned distribution versions, in addition to
existing source/template/payload hashes and the full `pip freeze` inventory.
Payload verification checks the lock hash even if the payload inventory was
refreshed. Installed smoke checks the bundled interpreter and distribution
metadata against the build record before exercising the live entry point.
Old manifests without the new lock hash remain readable by the integrity
verifier; all newly built payloads include it.

The installer workflow is no longer tied to PR number 126. As of 2026-10-29,
ordinary PR updates skip the installer job and produce no EXE artifact. Source
and Vision workflows continue independently. For a substantial testing release,
explicitly run `Windows test installer` using `workflow_dispatch` on the desired
branch, or deliberately update `packaging/installer-release-request.txt` in the
HEAD commit. Only a request-file change in that commit triggers a PR build;
subsequent ordinary commits skip it. Request text ships as TEST_RELEASE_NOTES.txt
and its hash is recorded and checked in the installed payload. That run exercises the unchanged build/extraction/spawn/Tk/live UI and
upgrade checks. A skipped PR installer job is not installation validation;
small source changes remain newer than the last distributed installer until the
next intentional build.

## Updating the contract

Update runtime constraints deliberately, update the workflow/builder Python
version together if changing the interpreter, and retain the successful Windows
run as version provenance. Rebuild and pass payload hashes, spawn, Tk and
installed live UI smoke before distributing a changed build. The `vision` and
development extras keep their existing ranges; this contract is specifically
for the Windows test installer.

This pins interpreter/runtime package versions, not an EXE byte-for-byte build:
timestamps, runner image, compiler and build tools are not all locked. Payload
hashes identify the exact artifact produced by each run.

## Local verification

Fourteen installer/dependency/payload/entrypoint tests passed, including
version drift, missing pins, malformed/duplicate constraints, dependency lookup
through a selected interpreter, and lock tampering despite re-inventory.
Packaging modules compile and diff whitespace checks pass.
Windows run `38365050572` at `44227501b373d4cb04f094e3090486f36a2e91c0`
passed pinned installation, EXE construction, extraction/hash verification,
spawn, Tk and installed live UI smoke. Artifact `11796625819` was produced.
The earlier all-green d492833 run establishes the version source.

Real mirrored-game identity accuracy, exact-hand coverage, end-to-end latency
and capture recovery still need a reviewed Windows session. Successful
installer smoke must not be substituted for that evidence.
