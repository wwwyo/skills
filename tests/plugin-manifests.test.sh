#!/usr/bin/env bash
# plugins/<plugin>/skills/ の dir から生成する Claude・Codex・pi・skillctrl の定義が最新で、全 skill をちょうど 1 回ずつ配ることを検査する
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 scripts/sync-plugin-manifests.py --check >/dev/null
python3 - <<'PYTHON'
import json
pi = json.load(open('package.json'))['pi']
assert pi == {'skills': ['./plugins/core/skills', './plugins/design/skills', './plugins/local/skills']}, f'pi package must load every plugin: {pi}'
PYTHON
echo "OK: plugin manifests are in sync"
