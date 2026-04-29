#!/bin/bash
set -e

REPO_PATH="/opt/repo/edo-boost-main.git"
LOCAL_REPO="/home/nkgolol/Dev/SandBox/edo-boost-main/edo-boost-main"

echo "Creating bare repository at $REPO_PATH..."
sudo mkdir -p "$REPO_PATH"
sudo chown -R $USER:$USER /opt/repo
cd "$REPO_PATH"
git init --bare

echo "Configuring local repository with a dedicated redmine remote..."
cd "$LOCAL_REPO"
# Add a dedicated redmine remote instead of modifying origin
if git remote | grep -q "^redmine$"; then
    git remote set-url redmine "$REPO_PATH"
else
    git remote add redmine "$REPO_PATH"
fi

echo "Repository setup complete!"
echo ""
echo "=========================================================================="
echo "To link commit IDs to changes in Redmine, follow these steps in the UI:"
echo "1. Go to your Redmine project: Settings -> Repositories."
echo "2. Click 'New repository'."
echo "3. SCM: Git"
echo "4. Main repository: Check the box."
echo "5. Identifier: edo-boost-main"
echo "6. Path to repository: $REPO_PATH"
echo "7. Click 'Create'."
echo ""
echo "To ensure Redmine fetches new commits automatically:"
echo "Go to Administration -> Settings -> Repositories."
echo "Ensure 'Enable WS for repository management' is checked and generate an API key."
echo "=========================================================================="
