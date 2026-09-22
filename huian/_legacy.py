"""Private compatibility facade for the current Huian runtime.

The live package no longer imports code from legacy_code or installs qzcore/qzenv
as top-level packages. Frozen historical baselines remain under legacy_code for
comparison tests only.
"""
from huian._compat import qzcore as core
from huian._compat import qzenv as env

__all__ = ["core", "env"]
