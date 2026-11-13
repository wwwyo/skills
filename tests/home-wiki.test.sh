#!/usr/bin/env bash
# project-setup の home-wiki.ts: 骨組みを置き、再実行で domain を足し、既存 file を壊さないこと
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
TOOL="$repo_dir/.agents/skills/project-setup/tools/home-wiki.ts"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
# home-wiki.ts と okf-check.ts は Bun で動く。bun の無い環境（CI の素の runner）では全体を飛ばす
if ! command -v bun >/dev/null; then echo "skip: bun が無いので home-wiki を検査しない" >&2; exit 0; fi
check_ok() { echo "$1" | jq -e '.check.ok == true' >/dev/null; }

git -C "$tmp" init -q
printf '# AGENTS.md\n\nexisting\n' >"$tmp/AGENTS.md"

out="$(bun "$TOOL" "$tmp" --domain "alpha=最初の domain")"
check_ok "$out" || fail "initial check: $out"
for f in raw/.gitkeep wiki/AGENTS.md wiki/CLAUDE.md wiki/index.md wiki/alpha/index.md tools/okf-check.ts; do
  [ -f "$tmp/$f" ] || fail "missing $f"
done
grep -q '^existing$' "$tmp/AGENTS.md" || fail "AGENTS.md lost existing content"
grep -q '^## メモリ（wiki）$' "$tmp/AGENTS.md" || fail "memory section not appended"
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
out="$(bun "$TOOL" "$tmp" --domain alpha --domain beta)"
check_ok "$out" || fail "rerun check: $out"
echo "$out" | jq -e '.updated | index("tools/okf-check.ts") != null' >/dev/null || fail "checker not updated: $out"
grep -q '"alpha", "beta"' "$tmp/tools/okf-check.ts" || fail "domains not merged"
grep -q '^local edit$' "$tmp/wiki/AGENTS.md" || fail "schema overwritten"
[ "$(grep -c '^## メモリ（wiki）$' "$tmp/AGENTS.md")" = 1 ] || fail "memory section duplicated"
grep -q '^\* \[beta\](./beta/index.md)$' "$tmp/wiki/index.md" || fail "beta Map row"

# 未定義 domain のページは検査で落ちる
sed 's/\[alpha\]/[gamma]/' "$tmp/wiki/alpha/page.md" >"$tmp/wiki/alpha/bad.md"
if bun "$tmp/tools/okf-check.ts" "$tmp/wiki" >/dev/null; then fail "undefined domain passed"; fi

# 引数の誤り
if bun "$TOOL" "$tmp" --domain 'Bad Name' 2>/dev/null; then fail "invalid domain accepted"; fi
# 未知の option・値の無い --domain も引数の誤り（exit 2）
set +e; bun "$TOOL" "$tmp" --nope >/dev/null 2>&1; c=$?; bun "$TOOL" "$tmp" --domain >/dev/null 2>&1; d=$?; set -e
[ "$c" = 2 ] && [ "$d" = 2 ] || fail "bad args exit: $c $d"
# 説明文の $ は置換パターンにせずそのまま Map に書く
fresh="$(mktemp -d)"; git -C "$fresh" init -q
bun "$TOOL" "$fresh" --domain 'gamma=a$&b$$c' >/dev/null || fail "dollar desc run"
grep -qF '* [gamma](./gamma/index.md) - a$&b$$c' "$fresh/wiki/index.md" || fail "dollar desc mangled: $(grep gamma "$fresh/wiki/index.md")"
rm -rf "$fresh"
# 読めない checker では何も書かずに exit 2
sed -i.bak 's/^const ALLOWED_DOMAINS = /const ALLOWED_DOMAINS: Set<string> = /' "$tmp/tools/okf-check.ts"
before="$(cat "$tmp/wiki/index.md")"
if bun "$TOOL" "$tmp" --domain delta 2>/dev/null; then fail "unparsable checker accepted"; fi
[ "$before" = "$(cat "$tmp/wiki/index.md")" ] || fail "index written before checker error"
[ ! -e "$tmp/wiki/delta" ] || fail "domain dir written before checker error"
echo "home-wiki: ok"
