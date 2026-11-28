#!/usr/bin/env python3
"""plugins/<plugin>/skills/ の実 dir を正本に、Claude・Codex の plugin 定義を生成・検査する。

usage: scripts/sync-plugin-manifests.py [--check]

- 正本: plugins/<plugin>/skills/<name>/（どの plugin に載るかは置き場所で決まる）と、
  .claude-plugin/marketplace.json の plugin entry（description・mcpServers 等は手で書く）
- 生成: marketplace.json の各 entry の source・strict・skills、
  .agents/plugins/marketplace.json、各 plugin の .codex-plugin/plugin.json
- 外部 plugin: source が object（github 等）の entry は別 repo の plugin として Claude の
  marketplace にだけ載せ、生成・検査の対象から外す（marketing = wwwyo/marketingskills）
- 検査: plugin entry と plugins/ の dir が一致し、各 skill dir は symlink でなく
  SKILL.md の name と dir 名が一致し、skill 名が plugin をまたいで重複しないこと

Codex は local plugin を ~/.codex/plugins/cache へコピーし、その際に symlink を落とすので、
plugin root（plugins/<plugin>）には実ファイルを置き、skills は root からの相対 path で列挙する。
Claude も plugin root だけを cache へコピーするので、skill は自分の plugin の外を参照できない
（tests/plugin-boundaries.test.sh が検査する）。

--check は差分・検査違反があれば stderr に理由を出して exit 1。書き込まない。
stdout には 1 行の JSON（{"changed": [...], "ok": bool}）を出す。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
CLAUDE = ROOT / ".claude-plugin/marketplace.json"
CODEX_MARKETPLACE = ROOT / ".agents/plugins/marketplace.json"
SKILLCTRL_CONFIG = ROOT / ".agents/skillctrl/config.json"
PI = ROOT / "package.json"
VERSION = "0.1.0"


def dump(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def skill_name(skill_dir: Path) -> str | None:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"(?m)^name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", text)
    return match.group(1) if match else None


def plugin_skills(plugin: str, errors: list[str]) -> list[str]:
    skills_dir = PLUGINS / plugin / "skills"
    names = []
    for path in sorted(skills_dir.iterdir()) if skills_dir.is_dir() else []:
        if path.name.startswith("."):
            continue
        if path.is_symlink() or not (path / "SKILL.md").is_file():
            errors.append(f"{path.relative_to(ROOT)}: must be a real skill dir with SKILL.md")
        elif skill_name(path) != path.name:
            errors.append(f"{path.relative_to(ROOT)}: SKILL.md name {skill_name(path)!r} differs from dir name")
        else:
            names.append(path.name)
    if not names:
        errors.append(f"plugins/{plugin}/skills: has no skills")
    return names


def main() -> int:
    check = sys.argv[1:] == ["--check"]
    if sys.argv[1:] not in ([], ["--check"]):
        print(__doc__, file=sys.stderr)
        return 2

    errors: list[str] = []
    marketplace = json.loads(CLAUDE.read_text(encoding="utf-8"))
    local = [p for p in marketplace["plugins"] if not isinstance(p.get("source"), dict)]
    plugins = [p["name"] for p in local]
    dirs = sorted(p.name for p in PLUGINS.iterdir() if p.is_dir())
    if sorted(plugins) != dirs:
        errors.append(f"marketplace plugins {sorted(plugins)} must match plugins/ dirs {dirs}")
    names = [p.get("name") for p in marketplace["plugins"]]
    for name in {n for n in names if names.count(n) > 1}:
        errors.append(f"marketplace plugin {name!r}: listed more than once")
    for entry in marketplace["plugins"]:
        source = entry.get("source")
        if isinstance(source, dict) and not (
            entry.get("name") and source.get("source") == "github" and source.get("repo", "").count("/") == 1
        ):
            errors.append(f"marketplace plugin {entry.get('name')!r}: external source must be github with owner/repo")

    seen: dict[str, str] = {}
    expected: dict[Path, str] = {}
    codex_entries = []
    for entry in local:
        name = entry["name"]
        skills = plugin_skills(name, errors)
        for skill in skills:
            if skill in seen:
                errors.append(f"{skill}: found in both {seen[skill]} and {name}")
            seen[skill] = name
        entry["source"] = f"./plugins/{name}"
        entry["strict"] = False
        entry["skills"] = [f"./skills/{skill}" for skill in skills]
        expected[PLUGINS / name / ".codex-plugin/plugin.json"] = dump({
            "name": name,
            "version": VERSION,
            "description": entry["description"],
            "author": {"name": marketplace["owner"]["name"], "url": marketplace["owner"]["url"]},
            "repository": "https://github.com/wwwyo/skills",
            "skills": entry["skills"],
        })
        codex_entries.append({
            "name": name,
            "source": {"source": "local", "path": f"./plugins/{name}"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        })
    expected[CLAUDE] = dump(marketplace)
    expected[CODEX_MARKETPLACE] = dump({
        "name": marketplace["name"],
        "interface": {"displayName": "wwwyo skills"},
        "plugins": codex_entries,
    })
    roots = {name: f"plugins/{name}/skills" for name in plugins}
    expected[SKILLCTRL_CONFIG] = dump({"version": 1, "skillRoots": roots})
    pi = json.loads(PI.read_text(encoding="utf-8"))
    pi["pi"]["skills"] = [f"./{root}" for root in roots.values()]
    expected[PI] = dump(pi)

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
