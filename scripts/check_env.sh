#!/usr/bin/env bash
set -euo pipefail

# scripts/check_env.sh — simple environment checks for local development
# Ensures `python` points to Python 3.11.x

REQUIRED_MAJOR=3
REQUIRED_MINOR=11

python_version_raw=$(python -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || true)
if [ -z "$python_version_raw" ]; then
  echo "ERROR: 'python' executable not found in PATH"
  exit 2
fi

IFS='.' read -r major minor patch <<< "$python_version_raw"
if [ "$major" -eq "$REQUIRED_MAJOR" ] && [ "$minor" -eq "$REQUIRED_MINOR" ]; then
  echo "OK: Python $python_version_raw"
  exit 0
else
  echo "ERROR: Python $python_version_raw detected. This project requires Python ${REQUIRED_MAJOR}.${REQUIRED_MINOR}."
  echo "Suggestion: use pyenv, virtualenv, or 'python3.11' in a venv."
  exit 3
fi
