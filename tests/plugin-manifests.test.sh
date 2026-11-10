#!/usr/bin/env bash
# Claude marketplace（正本）と Codex の plugin 定義が一致し、全 skill をちょうど 1 回ずつ配ることを検査する
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 scripts/sync-plugin-manifests.py --check >/dev/null
python3 - <<'PYTHON'
import json
pi = json.load(open('package.json'))['pi']
assert pi == {'skills': ['./.agents/skills']}, f'pi package must load .agents/skills: {pi}'
PYTHON
echo "OK: plugin manifests are in sync"
