#!/usr/bin/env bash
# domain-modeling の可視化生成器が例の入力を読み、3部のデータと HTML を出すことを検査する。
set -euo pipefail
cd "$(dirname "$0")/.."
SKILL=.agents/skills/domain-modeling
TOOL=$SKILL/tools/domain_viz.py
EX=$SKILL/assets/domain-viz-example
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

python3 "$TOOL" --types "$EX/model.ts" --spec "$EX/viz.json" --dump >"$tmp/data.json"
python3 - "$tmp/data.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
aggs = {a["name"]: a for a in d["aggregates"]}
assert list(aggs) == ["顧客", "注文", "返品"], list(aggs)
assert [b["name"] for b in aggs["注文"]["boxes"]] == ["注文", "明細", "支払い", "カード払い", "振込"]
assert aggs["返品"]["proposed"] and not aggs["注文"]["proposed"]
assert aggs["注文"]["rule"] == "明細は1件以上。キャンセル後は明細を変えない"
rows = {r[0]: r for r in aggs["注文"]["boxes"][0]["rows"]}
assert rows["注文ID"][4] == "PK" and rows["注文ID"][5] == "id"
assert rows["顧客"][4] == "FK" and rows["状態"][5] == "enum" and rows["明細"][5] == "arr"
assert aggs["返品"]["boxes"][0]["rows"][0][4] == "PK・FK"
assert rows["支払い"][5] == "obj"
pay = {r[0]: r for r in aggs["注文"]["boxes"][4]["rows"]}
assert pay["入金日"][1] is True  # optional
# 都道府県 has 13 literals (> inline limit) so it becomes its own box
assert "都道府県" in [b["name"] for b in aggs["顧客"]["boxes"]]
ov = {a["name"]: a for a in d["overview"]["aggregates"]}
assert ov["注文"]["invariant"] == "明細は1件以上"            # spec override
assert ov["顧客"]["responsibility"] == "注文する人"          # from title
assert {"from": "返品", "to": "注文", "label": ""} in d["overview"]["refs"]  # auto refs
assert len(d["db"]["domains"]) == 3
EOF

python3 "$TOOL" --types "$EX/model.ts" --spec "$EX/viz.json" --out "$tmp/out.html" >/dev/null
grep -q '"title": "通販のドメイン（例）"' "$tmp/out.html"
! grep -q '__DATA__\|__ICONS__\|__TITLE__' "$tmp/out.html"

# bad references fail with a message instead of drawing a broken page
sed 's/"ref": "product"/"ref": "nope"/' "$EX/viz.json" >"$tmp/bad.json"
if python3 "$TOOL" --types "$EX/model.ts" --spec "$tmp/bad.json" --out "$tmp/bad.html" 2>"$tmp/err"; then
  echo "expected failure for unknown ref" >&2; exit 1
fi
grep -q "unknown table 'nope'" "$tmp/err"

echo "domain-viz: ok"
