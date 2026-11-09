#!/usr/bin/env python3
"""Claude の marketplace.json を正本に、Codex の plugin 定義を生成・検査する。

usage: scripts/sync-plugin-manifests.py [--check]

- 正本: .claude-plugin/marketplace.json（plugin ごとの skills 一覧）
- 生成: .agents/plugins/marketplace.json と各 plugin root の .codex-plugin/plugin.json
- 検査: .agents/skills/ の実 dir（symlink の alias は除く）がどれか 1 つの plugin に
  ちょうど 1 回載り、載っている skill は SKILL.md の name と dir 名が一致すること

Codex は local plugin を ~/.codex/plugins/cache へコピーし、その際に symlink を落とす。
そのため plugin root は実ファイルを含む dir にし（core = repo root、local = .agents）、
skills は root からの相対 path で 1 つずつ列挙する。

--check は差分・検査違反があれば stderr に理由を出して exit 1。書き込まない。
stdout には 1 行の JSON（{"changed": [...], "ok": bool}）を出す。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".agents/skills"
CLAUDE = ROOT / ".claude-plugin/marketplace.json"
CODEX_MARKETPLACE = ROOT / ".agents/plugins/marketplace.json"
# plugin 名 → Codex の plugin root（repo root からの相対）
CODEX_ROOTS = {"core": ".", "local": ".agents"}
VERSION = "0.1.0"


def dump(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def skill_name(skill_dir: Path) -> str | None:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"(?m)^name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", text)
    return match.group(1) if match else None


def main() -> int:
    check = sys.argv[1:] == ["--check"]
    if sys.argv[1:] not in ([], ["--check"]):
        print(__doc__, file=sys.stderr)
        return 2

    errors: list[str] = []
    marketplace = json.loads(CLAUDE.read_text(encoding="utf-8"))
    plugins = marketplace["plugins"]
    names = [p["name"] for p in plugins]
    if sorted(names) != sorted(CODEX_ROOTS):
        errors.append(f"plugins {names} must match CODEX_ROOTS {sorted(CODEX_ROOTS)}")

    seen: dict[str, str] = {}
    for plugin in plugins:
        if plugin.get("source") != "./" or plugin.get("strict") is not False:
            errors.append(f"{plugin['name']}: source must be './' and strict false")
        for entry in plugin["skills"]:
            prefix = "./.agents/skills/"
            if not entry.startswith(prefix) or "/" in entry[len(prefix):]:
                errors.append(f"{plugin['name']}: {entry} must be {prefix}<name>")
                continue
            name = entry[len(prefix):]
            path = SKILLS / name
            if name in seen:
                errors.append(f"{name}: listed in both {seen[name]} and {plugin['name']}")
            seen[name] = plugin["name"]
            if path.is_symlink() or not (path / "SKILL.md").is_file():
                errors.append(f"{name}: must be a real skill dir with SKILL.md (alias symlinks are not listed)")
            elif skill_name(path) != name:
                errors.append(f"{name}: SKILL.md name {skill_name(path)!r} differs from dir name")

    for path in sorted(SKILLS.iterdir()):
        if path.is_dir() and not path.is_symlink() and (path / "SKILL.md").is_file() and path.name not in seen:
            errors.append(f"{path.name}: not listed in any plugin of {CLAUDE.relative_to(ROOT)}")

    expected: dict[Path, str] = {}
    codex_entries = []
    for plugin in plugins:
        root = CODEX_ROOTS.get(plugin["name"])
        if root is None:
            continue
        root_dir = (ROOT / root).resolve()
        skills = []
        for entry in plugin["skills"]:
            rel = (ROOT / entry).resolve().relative_to(root_dir).as_posix()
            skills.append(f"./{rel}")
        expected[root_dir / ".codex-plugin/plugin.json"] = dump({
            "name": plugin["name"],
            "version": VERSION,
            "description": plugin["description"],
            "author": {"name": marketplace["owner"]["name"], "url": marketplace["owner"]["url"]},
            "repository": "https://github.com/wwwyo/skills",
            "skills": skills,
        })
        codex_entries.append({
            "name": plugin["name"],
            "source": {"source": "local", "path": "./" if root == "." else f"./{root}"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        })
    expected[CODEX_MARKETPLACE] = dump({
        "name": marketplace["name"],
        "interface": {"displayName": "wwwyo skills"},
        "plugins": codex_entries,
    })

    changed = []
    for path, content in expected.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            changed.append(path.relative_to(ROOT).as_posix())
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
    if check:
        errors += [f"{p}: out of date; run scripts/sync-plugin-manifests.py" for p in changed]

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    print(json.dumps({"changed": changed, "ok": not errors}))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
