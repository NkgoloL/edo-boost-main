#!/bin/bash

# Git Sync Verification Script
# This script checks if the local repository is in sync with GitHub and the Redmine mirror.

LOCAL_HEAD=$(git rev-parse HEAD)
GITHUB_URL="git@github.com:NkgoloL/edo-boost-main.git"
REDMINE_PATH="/opt/repo/edo-boost-main.git"

echo "Local HEAD: $LOCAL_HEAD"

echo "Checking GitHub (origin)..."
# Note: This might prompt for passphrase if not in ssh-agent
REMOTE_GITHUB=$(git ls-remote --heads origin main 2>/dev/null | awk '{print $1}')
if [ -z "$REMOTE_GITHUB" ]; then
    echo "[STUCK] GitHub is unreachable or requires authentication."
    echo "        Ensure ssh-agent is running and your key is added."
elif [ "$LOCAL_HEAD" == "$REMOTE_GITHUB" ]; then
    echo "[OK] GitHub is in sync with local main."
else
    echo "[FAIL] GitHub is NOT in sync!"
    echo "  GitHub main: $REMOTE_GITHUB"
    echo "  Local main:  $LOCAL_HEAD"
fi

echo ""
echo "Checking Redmine Mirror (redmine)..."
if git remote | grep -q "^redmine$"; then
    REMOTE_REDMINE=$(git ls-remote --heads redmine main 2>/dev/null | awk '{print $1}')
    if [ -z "$REMOTE_REDMINE" ]; then
        echo "[FAIL] Redmine mirror path not found or inaccessible."
    elif [ "$LOCAL_HEAD" == "$REMOTE_REDMINE" ]; then
        echo "[OK] Redmine mirror is in sync."
    else
        echo "[FAIL] Redmine mirror is NOT in sync!"
        echo "  Redmine main: $REMOTE_REDMINE"
    fi
else
    echo "[SKIP] Redmine remote not configured."
fi

echo ""
echo "--- Suggestion ---"
echo "To sync everything, run:"
echo "  git push origin main && git push redmine main"
