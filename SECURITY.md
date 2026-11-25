# Security policy

This project is experimental. Hint Alpha is internal/read-only and Executor is
OFF. Vision uncertainty must suppress advice and must never trigger live clicks.

## Reporting

Do not put credentials, private game recordings, account identifiers or an
exploitable vulnerability in a public issue. Use GitHub's private vulnerability
reporting interface when available. If it is unavailable, ask the maintainer for
a private reporting channel without publishing sensitive details. No private
contact address or response-time guarantee has been established.

## Checks and boundaries

- CodeQL Python security analysis is configured for pull requests, main pushes
  and weekly runs. The first successful run must be checked before claiming
  scanning is operational. GitHub Default setup may need disabling if it
  conflicts with this advanced workflow.
- CI runs fatal-error lint, tests, evidence contracts and installed wheel checks.
- Secret-scanning and repository push-protection settings are separate GitHub
  controls; workflow files do not enable or verify them.
- Root Dependabot covers pyproject dependencies including optional extras;
  the capture validator's separate requirements manifest has its own update job.
- Screenshots and client-derived templates have separate provenance and rights
  questions; see `docs/material_rights.md`.
