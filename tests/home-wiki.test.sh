#!/usr/bin/env bash
# project-setup の home_wiki.py: 骨組みを置き、再実行で domain を足し、既存 file を壊さないこと
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
TOOL="$repo_dir/.agents/skills/project-setup/tools/home_wiki.py"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

git -C "$tmp" init -q
printf '# AGENTS.md\n\nexisting\n' >"$tmp/AGENTS.md"

out="$(python3 "$TOOL" "$tmp" --domain "alpha=最初の domain")"
echo "$out" | jq -e '.check.ok == true' >/dev/null || fail "initial check: $out"
for f in raw/.gitkeep wiki/AGENTS.md wiki/CLAUDE.md wiki/index.md wiki/alpha/index.md tools/okf_check.py; do
  [ -f "$tmp/$f" ] || fail "missing $f"
done
grep -q '^existing$' "$tmp/AGENTS.md" || fail "AGENTS.md lost existing content"
grep -q '^## メモリ（wiki）$' "$tmp/AGENTS.md" || fail "memory section not appended"
grep -qx '\*.local.\*' "$tmp/.gitignore" || fail ".gitignore lacks *.local.*"
grep -q '^\* \[alpha\](./alpha/index.md) - 最初の domain$' "$tmp/wiki/index.md" || fail "Map row"

# ページを書いて検査が domain を認めること
cat >"$tmp/wiki/alpha/page.md" <<'MD'
---
type: concept
title: Page
description: テスト用のページ。
tags: [alpha]
---

本文
MD
echo '* [Page](page.md) - テスト' >>"$tmp/wiki/alpha/index.md"

# 再実行で domain を足す。既存の index・schema は上書きしない
echo 'local edit' >>"$tmp/wiki/AGENTS.md"
out="$(python3 "$TOOL" "$tmp" --domain alpha --domain beta)"
echo "$out" | jq -e '.check.ok == true' >/dev/null || fail "rerun check: $out"
echo "$out" | jq -e '.updated | index("tools/okf_check.py") != null' >/dev/null || fail "checker not updated: $out"
grep -q '"alpha", "beta"' "$tmp/tools/okf_check.py" || fail "domains not merged"
grep -q '^local edit$' "$tmp/wiki/AGENTS.md" || fail "schema overwritten"
[ "$(grep -c '^## メモリ（wiki）$' "$tmp/AGENTS.md")" = 1 ] || fail "memory section duplicated"
grep -q '^\* \[beta\](./beta/index.md)$' "$tmp/wiki/index.md" || fail "beta Map row"

# 未定義 domain のページは検査で落ちる
sed 's/\[alpha\]/[gamma]/' "$tmp/wiki/alpha/page.md" >"$tmp/wiki/alpha/bad.md"
if python3 "$tmp/tools/okf_check.py" "$tmp/wiki" >/dev/null; then fail "undefined domain passed"; fi

# 引数の誤り
if python3 "$TOOL" "$tmp" --domain 'Bad Name' 2>/dev/null; then fail "invalid domain accepted"; fi
echo "home-wiki: ok"
