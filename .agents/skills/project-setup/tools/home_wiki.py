#!/usr/bin/env python3
"""home repo に memory（LLM wiki）の骨組みを置く・domain を足す。

使い方:
  home_wiki.py <home-dir> --domain <name>[=<説明>] [--domain ...] [--dry-run]

置くもの（既存の file は上書きしない）:
  raw/.gitkeep, wiki/AGENTS.md（schema）, wiki/CLAUDE.md, wiki/index.md（Map）,
  wiki/<domain>/index.md, tools/okf-check.ts（検査。Bun で実行）, root AGENTS.md の「メモリ（wiki）」節
既存の wiki/index.md と tools/okf-check.ts には、足りない domain だけを追記する。
最後に bun tools/okf-check.ts wiki を実行し、結果を stdout に 1 行の JSON で返す。
検査が通らなければ exit 1、引数の誤りは exit 2。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "home-wiki"
DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DOMAINS_LINE = re.compile(r"^const ALLOWED_DOMAINS = new Set\(\[([^\]]*)\]\);", re.MULTILINE)
MEMORY_HEADING = "## メモリ（wiki）"


def parse_domain(raw: str) -> tuple[str, str]:
    name, _, desc = raw.partition("=")
    name = name.strip()
    if not DOMAIN_RE.match(name):
        raise ValueError(f"invalid domain: {name!r}（小文字英数字と - のみ）")
    return name, desc.strip()


def map_row(name: str, desc: str) -> str:
    return f"* [{name}](./{name}/index.md)" + (f" - {desc}" if desc else "")


def domains_literal(names: list[str]) -> str:
    return ", ".join(f'"{n}"' for n in sorted(names))


class Plan:
    def __init__(self, dry_run: bool):
        self.dry_run = dry_run
        self.created: list[str] = []
        self.updated: list[str] = []
        self.home: Path = Path()

    def write(self, path: Path, text: str, *, new: bool) -> None:
        (self.created if new else self.updated).append(str(path.relative_to(self.home)))
        if self.dry_run:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def ensure_index(plan: Plan, path: Path, domains: list[tuple[str, str]]) -> None:
    if not path.exists():
        rows = "\n".join(map_row(n, d) for n, d in domains)
        plan.write(path, (ASSETS / "index.md").read_text(encoding="utf-8").replace("__MAP__", rows), new=True)
        return
    text = path.read_text(encoding="utf-8")
    missing = [(n, d) for n, d in domains if f"](./{n}/index.md)" not in text]
    if not missing:
        return
    lines = text.split("\n")
    # Map 節の最後の行頭 `* [` の直後へ足す。Map 節が無ければ末尾に作る
    try:
        start = lines.index("## Map")
    except ValueError:
        lines += ["", "## Map", ""]
        start = len(lines) - 2
    insert_at = start + 1
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            break
        if lines[i].startswith("* ["):
            insert_at = i + 1
    if insert_at == start + 1:
        lines.insert(insert_at, "")
        insert_at += 1
    lines[insert_at:insert_at] = [map_row(n, d) for n, d in missing]
    plan.write(path, "\n".join(lines), new=False)


def ensure_checker(plan: Plan, path: Path, names: list[str]) -> None:
    if not path.exists():
        text = (ASSETS / "okf-check.ts").read_text(encoding="utf-8")
        plan.write(path, text.replace("__DOMAINS__", domains_literal(names)), new=True)
        if not plan.dry_run:
            path.chmod(0o755)
        return
    text = path.read_text(encoding="utf-8")
    m = DOMAINS_LINE.search(text)
    if not m:
        raise RuntimeError(f"{path}: const ALLOWED_DOMAINS = new Set([...]); の行が見つからない")
    current = set(re.findall(r'"([^"]+)"', m.group(1)))
    if set(names) <= current:
        return
    new_line = f"const ALLOWED_DOMAINS = new Set([{domains_literal(sorted(current | set(names)))}]);"
    plan.write(path, text[: m.start()] + new_line + text[m.end():], new=False)


def ensure_agents_memory(plan: Plan, path: Path) -> None:
    section = (ASSETS / "agents-memory.md").read_text(encoding="utf-8")
    if not path.exists():
        plan.write(path, "# AGENTS.md\n\n" + section, new=True)
        return
    text = path.read_text(encoding="utf-8")
    if MEMORY_HEADING in text:
        return
    plan.write(path, text.rstrip("\n") + "\n\n" + section, new=False)


def ensure_file(plan: Plan, path: Path, text: str) -> None:
    if not path.exists():
        plan.write(path, text, new=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold an LLM wiki memory in a home repo.")
    parser.add_argument("home", help="home repo の root")
    parser.add_argument("--domain", action="append", required=True,
                        help="<name>[=<Map に載せる説明>]。複数指定できる")
    parser.add_argument("--dry-run", action="store_true", help="書かずに作成・更新する file だけを返す")
    args = parser.parse_args()

    home = Path(args.home).expanduser().resolve()
    try:
        domains = [parse_domain(d) for d in args.domain]
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if not (home / ".git").exists():
        print(json.dumps({"error": f"not a git repository: {home}"}, ensure_ascii=False), file=sys.stderr)
        return 2

    # 既存 checker の domain 行を読めないなら、何も書く前に止める（途中まで書いた状態を残さない）
    checker = home / "tools" / "okf-check.ts"
    if checker.exists() and not DOMAINS_LINE.search(checker.read_text(encoding="utf-8")):
        print(json.dumps({"error": f"{checker}: const ALLOWED_DOMAINS = new Set([...]); の形の定義が見つからない。手で domain を足すかこの形に戻してから再実行する"},
                         ensure_ascii=False), file=sys.stderr)
        return 2

    plan = Plan(args.dry_run)
    plan.home = home
    names = [n for n, _ in domains]
    wiki = home / "wiki"

    ensure_file(plan, home / "raw" / ".gitkeep", "")
    ensure_file(plan, wiki / "AGENTS.md", (ASSETS / "wiki-AGENTS.md").read_text(encoding="utf-8"))
    ensure_file(plan, wiki / "CLAUDE.md", "read @AGENTS.md\n")
    ensure_index(plan, wiki / "index.md", domains)
    for name, desc in domains:
        ensure_file(plan, wiki / name / "index.md", (desc or name) + "\n")
    ensure_checker(plan, checker, names)
    ensure_agents_memory(plan, home / "AGENTS.md")

    result: dict = {"home": str(home), "dry_run": args.dry_run,
                    "created": plan.created, "updated": plan.updated}
    code = 0
    if not args.dry_run:
        bun = shutil.which("bun")
        if bun is None:
            result["check"] = {"ok": False, "output": "bun が見つからない。mise で入れてから bun tools/okf-check.ts wiki を実行する"}
            code = 1
        else:
            r = subprocess.run([bun, "tools/okf-check.ts", "wiki"], cwd=home, capture_output=True, text=True)
            result["check"] = {"ok": r.returncode == 0, "output": r.stdout.strip()}
            code = 0 if r.returncode == 0 else 1
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
