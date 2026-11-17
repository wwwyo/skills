#!/usr/bin/env python3
"""design.md の token からアプリ側の lint 設定を生成する。

agent がいなくても CI と editor で design.md 準拠を強制するため、design.md の
fenced ```css block から token を分類し、stylelint と ESLint の設定 module を書き出す。
生成物は design.md の派生物（`## Exports`）で、手で編集しない。

lint-setup.py <design.md> [--out <dir>] [--exports <glob>]... [--tailwind-entry <css>]
              [--targets stylelint,eslint] [--check] [--dry-run] [--json]

- stylelint: 色リテラルの禁止（hex・色関数・named color）と、property ごとの許可値
  （design.md の token の var() と design.md に書かれたリテラル）を built-in rule だけで組む
- ESLint: JSX の style 属性の色・寸法リテラルを built-in の no-restricted-syntax で禁止する。
  --tailwind-entry を渡すと eslint-plugin-better-tailwindcss で任意値・既定 palette を禁止する
- --check: 生成物が design.md と一致するかだけを確認し、ずれていれば exit 1（CI 用）

このファイルが正本。consumer はコピーせずここを直接実行する。詳細は README.md 参照。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from check_common import spec_text

STYLELINT_FILE = "design-md.stylelint.mjs"
ESLINT_FILE = "design-md.eslint.mjs"

COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
CUSTOM_PROP_RE = re.compile(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;{}]+);")
DECL_RE = re.compile(r"(?<![\w-])([a-z][a-z-]*)\s*:\s*([^;{}]+);")
VAR_RE = re.compile(r"var\(\s*(--[a-zA-Z0-9_-]+)")

COLOR_FUNCS = ["rgb", "rgba", "hsl", "hsla", "hwb", "lab", "lch", "oklab", "oklch", "color"]
COLOR_VALUE_RE = re.compile(r"^(#[0-9a-fA-F]{3,8}|(?:%s)\(|color-mix\()" % "|".join(COLOR_FUNCS))
NUMERIC_VALUE_RE = re.compile(r"^-?\d*\.?\d+[a-z%]*$|^calc\(")
SHADCN_COLOR_NAMES = {
    "background", "foreground", "card", "popover", "primary", "secondary", "muted",
    "accent", "destructive", "border", "input", "ring", "chart", "sidebar",
}
GLOBAL_KEYWORDS = ["inherit", "initial", "unset", "revert", "revert-layer"]

# property group → (正規表現の property 名, token 分類, group 固有の許可 keyword)
GROUPS = {
    "color": (
        r"^(color|background-color|border(-(top|right|bottom|left|block|inline)(-(start|end))?)?-color"
        r"|outline-color|text-decoration-color|caret-color|accent-color|column-rule-color|fill|stroke)$",
        "color",
        ["currentcolor", "currentColor", "transparent", "none"],
    ),
    "font-family": (r"^font-family$", "font-family", []),
    "font-size": (r"^font-size$", "font-size", []),
    "line-height": (r"^line-height$", "line-height", ["normal"]),
    "letter-spacing": (r"^letter-spacing$", "letter-spacing", ["normal"]),
    "spacing": (
        r"^(margin|padding)(-(top|right|bottom|left|block|inline)(-(start|end))?)?$|^(gap|row-gap|column-gap)$",
        "spacing",
        ["0", "auto"],
    ),
    "radius": (
        r"^border(-(top|bottom|start|end)-(left|right|start|end))?-radius$",
        "radius",
        ["0"],
    ),
    "shadow": (r"^box-shadow$", "shadow", ["none"]),
    "duration": (r"^(transition|animation)-duration$", "duration", ["0s"]),
    "easing": (r"^(transition|animation)-timing-function$", "easing", []),
}

# Tailwind の既定 palette。design.md に同名の色 token が無ければ使用を禁止する
TAILWIND_PALETTE = [
    "slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber", "yellow", "lime",
    "green", "emerald", "teal", "cyan", "sky", "blue", "indigo", "violet", "purple",
    "fuchsia", "pink", "rose", "black", "white",
]
TAILWIND_COLOR_UTILS = (
    "bg|text|border(?:-[xytrblse])?|ring|ring-offset|outline|fill|stroke|from|via|to"
    "|decoration|divide|placeholder|caret|accent|shadow|inset-shadow"
)


def classify(name: str, value: str) -> str | None:
    """custom property を GROUPS の token 分類へ振り分ける。分類できなければ None。"""
    n = name[2:].lower()
    v = value.strip().lower()
    if n.startswith(("font-size", "text-")) and "line-height" not in n:
        return "font-size"
    if n.startswith(("line-height", "leading")) or n.endswith("line-height"):
        return "line-height"
    if n.startswith(("letter-spacing", "tracking")):
        return "letter-spacing"
    if n.startswith("font-weight"):
        return None
    if n.startswith("font"):
        return "font-family"
    if n.startswith(("space", "spacing", "gap")):
        return "spacing"
    if n.startswith("radius"):
        return "radius"
    if n.startswith("shadow"):
        return "shadow"
    if n.startswith(("duration", "motion-duration")):
        return "duration"
    if n.startswith(("ease", "easing", "motion-ease")) or v.startswith("cubic-bezier("):
        return "easing"
    if COLOR_VALUE_RE.match(v):
        return "color"
    # 名前だけで色とみなすのは値が寸法・数値でないときに限る（--sidebar-width 等を除く）
    if (n.startswith("color-") or n.split("-")[0] in SHADCN_COLOR_NAMES) and not NUMERIC_VALUE_RE.match(v):
        return "color"
    return None


def parse_design(css: str) -> tuple[dict[str, str], dict[str, set[str]]]:
    """design.md の css から (token 名 → 分類 or "", group → 許可リテラル) を返す。

    custom property は token、通常の declaration（Components の値）はその group で
    承認済みのリテラルとして扱う。design.md に書かれた値は設計者が承認した値だから。
    """
    css = COMMENT_RE.sub("", css)
    tokens: dict[str, str] = {}
    raw_values: dict[str, str] = {}
    for m in CUSTOM_PROP_RE.finditer(css):
        raw_values[m.group(1)] = m.group(2).strip()
    for name, value in raw_values.items():
        cat = classify(name, value)
        if cat is None:
            ref = VAR_RE.match(value)
            if ref and ref.group(1) in raw_values:
                cat = classify(ref.group(1), raw_values[ref.group(1)])
        tokens[name] = cat or ""

    literals: dict[str, set[str]] = {g: set() for g in GROUPS}
    for m in DECL_RE.finditer(css):
        prop, value = m.group(1), m.group(2).strip()
        for group, (prop_re, _, _) in GROUPS.items():
            if group == "color" or not re.match(prop_re, prop):
                continue
            if group == "font-family":
                continue  # font stack は token 経由に限る
            for part in split_value(value):
                if not part.startswith(("var(", "calc(")):
                    literals[group].add(part)
    return tokens, literals


def split_value(value: str) -> list[str]:
    """空白区切りの値を括弧の内側を壊さずに分割する。"""
    parts, depth, cur = [], 0, ""
    for ch in value:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch.isspace() and depth == 0:
            if cur:
                parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return [p for p in parts if p != "!important"]


def value_pattern(token_names: list[str], literals: list[str], keywords: list[str], allow_calc: bool = True) -> str:
    """property の値全体が許可された部品の空白区切りであることを表す正規表現を返す。"""
    var_alt = "|".join(re.escape(n[2:]) for n in sorted(token_names))
    token = rf"var\(--(?:{var_alt})\)" if var_alt else None
    calc_inner = rf"(?:{token}|\d*\.?\d+|[\s*/+-])+" if token else None
    alts = []
    if token:
        alts.append(token)
        if allow_calc:  # calc は token と単位なしの数だけで組む（calc(13px) を通さない）
            alts.append(rf"calc\({calc_inner}\)")
    alts += [re.escape(x) for x in sorted(set(literals) | set(keywords))]
    part = "(?:" + "|".join(alts) + ")"
    return rf"/^{part}(?:\s+{part})*$/"


def build_stylelint(tokens: dict[str, str], literals: dict[str, set[str]], exports: list[str]) -> dict:
    allowed = {}
    uncategorized = [n for n, c in tokens.items() if not c]
    for group, (prop_re, cat, keywords) in GROUPS.items():
        names = [n for n, c in tokens.items() if c == cat]
        if not names:
            continue  # design.md が定めていない分類は縛らない
        pool = names if group == "color" else names + uncategorized
        allowed[f"/{prop_re}/"] = [
            value_pattern(pool, sorted(literals.get(group, ())), keywords + GLOBAL_KEYWORDS, group != "color")
        ]
    color_msg = "design.md の色 token を var(--name) で使う（色リテラル禁止）"
    rules: dict = {
        "color-no-hex": [True, {"message": color_msg}],
        "color-named": ["never", {"message": color_msg}],
        "function-disallowed-list": [COLOR_FUNCS, {"message": color_msg}],
    }
    if allowed:
        rules["declaration-property-value-allowed-list"] = [
            allowed,
            {"message": "design.md の token（var(--name)）か design.md に書かれた値だけを使う"},
        ]
    disallowed = {}
    if any(c == "duration" for c in tokens.values()):
        disallowed["/^(transition|animation)$/"] = [r"/(^|[\s,])\d*\.?\d+m?s(?=[\s,]|$)/"]
    if any(c == "easing" for c in tokens.values()):
        disallowed.setdefault("/^(transition|animation)$/", []).append(r"/cubic-bezier\(/")
    if any(c == "font-size" for c in tokens.values()):
        disallowed["/^font$/"] = [r"/\d(px|rem|pt)\b/"]
    if disallowed:
        rules["declaration-property-value-disallowed-list"] = [
            disallowed,
            {"message": "shorthand でも design.md の motion・font-size token を使う"},
        ]
    config: dict = {"rules": rules}
    if exports:
        config["overrides"] = [
            {"files": exports, "rules": {r: None for r in rules}},
        ]
    return config


def build_eslint(tokens: dict[str, str], tailwind_entry: str | None) -> list[dict]:
    color_re = r"#[0-9a-fA-F]{3,8}|\b(?:" + "|".join(COLOR_FUNCS) + r")\("
    dim_props = r"^(margin|padding|gap|rowGap|columnGap|fontSize|lineHeight|letterSpacing|borderRadius|fontFamily)"
    style = "JSXAttribute[name.name='style']"
    restricted = [
        {
            "selector": f"{style} Literal[value=/{color_re}/]",
            "message": "style 属性に色リテラルを書かない。design.md の token を var(--name) で使う",
        },
        {
            "selector": f"{style} Property[key.name=/{dim_props}/] > Literal:not([value=/^var\\(--/])",
            "message": "style 属性の寸法・書体は design.md の token を var(--name) で使う",
        },
    ]
    configs: list[dict] = [
        {"files": ["**/*.{js,jsx,ts,tsx,mjs,cjs}"], "rules": {"no-restricted-syntax": ["error", *restricted]}}
    ]
    if tailwind_entry:
        color_tokens = {n[2:].removeprefix("color-") for n, c in tokens.items() if c == "color"}
        palette = [p for p in TAILWIND_PALETTE if p not in color_tokens]
        restrict = [
            {
                "pattern": r"\[([^\[\]]*?)\](?!:)",
                "message": "Tailwind の任意値は使わない。design.md の token を @theme 経由で使う",
            }
        ]
        if palette:
            restrict.append(
                {
                    "pattern": rf"^([a-zA-Z0-9:/_-]*:)?-?({TAILWIND_COLOR_UTILS})-({'|'.join(palette)})(-\d+)?(\/\d+)?$",
                    "message": "Tailwind の既定 palette は使わない。design.md の色 token を使う",
                }
            )
        configs.append(
            {
                "files": ["**/*.{js,jsx,ts,tsx,mjs,cjs,html,vue,svelte,astro}"],
                "plugins": {"better-tailwindcss": "__BETTER_TAILWINDCSS__"},
                "settings": {"better-tailwindcss": {"entryPoint": tailwind_entry}},
                "rules": {
                    "better-tailwindcss/no-restricted-classes": ["error", {"restrict": restrict}],
                    "better-tailwindcss/no-unknown-classes": ["error", {"detectComponentClasses": True}],
                },
            }
        )
    return configs


HEADER = (
    "// Generated by design-md/tools/lint-setup.py from {spec}. Do not edit.\n"
    "// design.md を変えたら lint-setup.py を再実行する（CI は --check で一致を確認する）。\n"
)


def render_stylelint(config: dict, spec: str) -> str:
    return HEADER.format(spec=spec) + "export default " + json.dumps(config, ensure_ascii=False, indent=2) + ";\n"


def render_eslint(configs: list[dict], spec: str, tailwind: bool) -> str:
    body = json.dumps(configs, ensure_ascii=False, indent=2)
    imports = ""
    if tailwind:
        body = body.replace('"__BETTER_TAILWINDCSS__"', "betterTailwindcss")
        imports = 'import betterTailwindcss from "eslint-plugin-better-tailwindcss";\n\n'
    return HEADER.format(spec=spec) + imports + "export default " + body + ";\n"


def generate(spec_path: Path, out_dir: Path, exports: list[str], tailwind_entry: str | None, targets: list[str]):
    tokens, literals = parse_design(spec_text(spec_path))
    rel_spec = spec_path.name
    files: dict[Path, str] = {}
    if "stylelint" in targets:
        files[out_dir / STYLELINT_FILE] = render_stylelint(build_stylelint(tokens, literals, exports), rel_spec)
    if "eslint" in targets:
        files[out_dir / ESLINT_FILE] = render_eslint(build_eslint(tokens, tailwind_entry), rel_spec, bool(tailwind_entry))
    categories: dict[str, list[str]] = {}
    for name, cat in tokens.items():
        categories.setdefault(cat or "uncategorized", []).append(name)
    return files, categories


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="design.md の token から stylelint / ESLint 設定を生成する")
    ap.add_argument("spec", type=Path, help="repo root の design.md")
    ap.add_argument("--out", type=Path, help="生成先 dir（既定: design.md と同じ dir）")
    ap.add_argument("--exports", action="append", default=[], metavar="GLOB",
                    help="token の実値を定義する派生物（tokens.css 等）。色リテラル禁止の対象外にする。複数可")
    ap.add_argument("--tailwind-entry", metavar="CSS", help="Tailwind v4 の entry CSS。指定時のみ Tailwind の rule を出す")
    ap.add_argument("--targets", default="stylelint,eslint", help="生成対象（カンマ区切り: stylelint,eslint）")
    ap.add_argument("--check", action="store_true", help="書き込まず、生成物が最新かだけを確認する（ずれは exit 1）")
    ap.add_argument("--dry-run", action="store_true", help="書き込まず、生成内容を表示する")
    ap.add_argument("--json", action="store_true", help="結果を JSON 1 行で出す")
    args = ap.parse_args(argv)

    if not args.spec.is_file():
        print(f"error: {args.spec} が見つからない", file=sys.stderr)
        return 2
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    unknown = [t for t in targets if t not in ("stylelint", "eslint")]
    if unknown or not targets:
        print(f"error: --targets は stylelint,eslint から選ぶ（不明: {unknown}）", file=sys.stderr)
        return 2
    out_dir = args.out or args.spec.resolve().parent
    if not out_dir.is_dir():
        print(f"error: {out_dir} が dir ではない", file=sys.stderr)
        return 2

    exports = list(args.exports)
    if args.tailwind_entry and args.tailwind_entry not in exports:
        exports.append(args.tailwind_entry)  # @theme に token の実値を書く派生物
    files, categories = generate(args.spec, out_dir, exports, args.tailwind_entry, targets)
    status: dict[str, str] = {}
    for path, content in files.items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == content:
            status[str(path)] = "unchanged"
        elif args.check:
            status[str(path)] = "stale" if current is not None else "missing"
        elif args.dry_run:
            status[str(path)] = "would-write"
        else:
            path.write_text(content, encoding="utf-8")
            status[str(path)] = "written"

    if args.dry_run and not args.json:
        for path, content in files.items():
            print(f"--- {path}\n{content}")
    result = {"files": status, "tokens": {k: sorted(v) for k, v in sorted(categories.items())}}
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        for path, st in status.items():
            print(f"{st} {path}")
        unc = categories.get("uncategorized")
        if unc:
            print(f"info uncategorized tokens（色以外の全 group で許可）: {', '.join(sorted(unc))}")
    if args.check and any(s in ("stale", "missing") for s in status.values()):
        print("error: 生成物が design.md とずれている。lint-setup.py を再実行する", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
