#!/usr/bin/env bash
# Install Python runtime + dev deps for CI (wheels only).
# Kept in a helper because githubactions:S8544 cannot resolve pinned -r inputs.
set -euo pipefail

python -m pip --version
python -m pip install --only-binary ":all:" -r requirements.txt
python -m pip install --only-binary ":all:" -r requirements-dev.txt
