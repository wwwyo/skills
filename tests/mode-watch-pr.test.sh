#!/usr/bin/env bash
# mode の watch-pr（Bun の TS）の test と型検査。bun の無い環境では飛ばす
set -euo pipefail
if ! command -v bun >/dev/null; then echo "skip: bun が無いので watch-pr を検査しない" >&2; exit 0; fi
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
# skill フォルダに node_modules を作ると skillctrl check が mode を drift と見るので、複製先で動かす
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
cp -R "$repo_dir/plugins/core/skills/mode/scripts/." "$work/"
cd "$work"
bun install --frozen-lockfile >/dev/null
bun test watch-pr
bun x tsc --project watch-pr/tsconfig.json --noEmit --strict
echo "OK: mode watch-pr"
