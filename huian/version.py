"""Project release identity.

This is intentionally separate from RuleSnapshot and agent versions:
- PROJECT_VERSION identifies the repository/package release;
- RuleSnapshot.fingerprint identifies the exact rule evidence snapshot;
- CURRENT_AGENT_VERSION identifies the promoted decision policy.
"""

PROJECT_NAME = "huian-mahjong-assistant"
PROJECT_VERSION = "0.2.0"


def project_manifest():
    return {
        "name": PROJECT_NAME,
        "version": PROJECT_VERSION,
    }
