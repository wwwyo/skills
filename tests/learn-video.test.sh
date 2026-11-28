#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
node --test "$repo_dir/plugins/core/skills/learn/scripts/am.test.mjs"
