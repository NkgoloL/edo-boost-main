#!/bin/bash

# Push to both GitHub (origin) and Redmine mirror
# This script ensures both remotes are updated.

echo "🚀 Pushing to GitHub (origin)..."
if git push origin main; then
    echo "✅ GitHub sync complete."
else
    echo "❌ GitHub sync failed."
    echo "   Suggestion: Run 'ssh-add ~/.ssh/id_ed25519' if prompted for passphrase."
fi

echo ""
echo "🚀 Pushing to Redmine (redmine)..."
if git push redmine main; then
    echo "✅ Redmine mirror sync complete."
else
    echo "❌ Redmine mirror sync failed."
fi

echo ""
echo "--- Sync Status ---"
bash "$(dirname "$0")/verify_sync.sh"
