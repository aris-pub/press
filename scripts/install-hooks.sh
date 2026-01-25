#!/bin/bash
# Install git hooks

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/hooks" && pwd)"
GIT_HOOKS_DIR=".git/hooks"

echo "Installing git hooks..."

# Install pre-commit hook
cp "$HOOKS_DIR/pre-commit" "$GIT_HOOKS_DIR/pre-commit"
chmod +x "$GIT_HOOKS_DIR/pre-commit"

echo "Git hooks installed successfully."
echo "The pre-commit hook will run 'just lint' before each commit."
