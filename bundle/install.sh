#!/usr/bin/env bash
# Install the governed revenue-ops skill into a Hermes skills directory.
set -euo pipefail
DEST="${1:-$HOME/.hermes/skills}"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DEST/revenue-ops-lead-to-revenue"
cp "$HERE/skills/revenue-ops-lead-to-revenue/SKILL.md" "$DEST/revenue-ops-lead-to-revenue/SKILL.md"
echo "Installed revenue-ops-lead-to-revenue -> $DEST/revenue-ops-lead-to-revenue/SKILL.md"
echo "Verify:  hermes skills list | grep revenue-ops    then invoke  /revenue-ops"
