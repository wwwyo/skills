#!/usr/bin/env python3
"""OKF v0.1 conformance + プロジェクト規約 lint + bundle 内 link 切れチェッカ（依存なし）。

使い方: python3 tools/okf_check.py [bundle_root]  (default: wiki)

wwwyo/skills の project-setup（tools/home_wiki.py）が home repo へ置いた copy。
置いた後は home 側が正本で、domain の追加はこの file の ALLOWED_DOMAINS を直接編集する。

検査内容:
  [§9-1]        予約名以外の全 .md が parseable な frontmatter を持つ（OKF 仕様）
  [§9-2]        frontmatter に非空の type がある（OKF 仕様）
  [type]        type が ALLOWED_TYPES に含まれる（プロジェクト規約）
  [domain]      tags 先頭が ALLOWED_DOMAINS かつ配置 dir 名と一致（プロジェクト規約）
  [field]       frontmatter のキーが ALLOWED_FIELDS のみ＝拡張フィールド禁止 + 重複キー検出（プロジェクト規約）
  [required]    title / description が非空（プロジェクト規約）
  [description] description が単文（。は最大1）（プロジェクト規約）
  [§6]          index.md は frontmatter を持たない（OKF 仕様）
  [link]        bundle 内 link 切れ + 相対内部リンク（bundle-absolute /... 違反）検知（index.md 含む）
                ただし gitignore 対象への link は違反にしない（件数のみ報告）。worktree /
                fresh clone には ignore されたページがコピーされないため、公開ページから
                `*.local.md` の実体がない場合をリンク切れと誤判定しないため
注: OKF §9 自体は type 非空のみ要求（consumer は未知 type を拒否すべきでない）。
ALLOWED_TYPES/ALLOWED_DOMAINS の enum 強制は producer 側の規約 lint であり、
バンドルは OKF valid のまま自分の語彙ドリフト（typo・表記揺れ）を防ぐためのもの。
新しい type/domain を導入するときはこの集合に追記する。
frontmatter は「1行スカラー + inline tags（`[a, b]`）」の限定文法を前提に正規表現で解析する
（YAML 非依存）。block 形式 tags・複数行値・引用符付き複雑値は使わない。
exit code: 違反があれば 1。

Python 3.9+ で動く（`from __future__ import annotations` で `dict[str, str] | None`
等の PEP604 記法を postponed evaluation にしているため、3.9 の `/usr/bin/python3`
でも import 時 TypeError にならない）。
"""
from __future__ import annotations

import argparse
import posixpath
import re
import subprocess
from pathlib import Path

# OKF 予約名 index.md に加え、本バンドルは AGENTS.md/CLAUDE.md を schema/instruction の
# 予約 meta として concept 扱いから除外する（OKF 予約集合のローカル拡張）。
RESERVED = {"index.md", "AGENTS.md", "CLAUDE.md", "index.local.md"}
# プロジェクト規約: 許可する type（form）と domain（tags 先頭）。増やすときはここに追記。
ALLOWED_TYPES = {"concept", "synthesis", "person", "company", "organization", "book"}
# domain（tags 先頭 = 配置 dir 名）。新しい domain を作るときはここに追記する。
# 撤退・完了した domain も削除しない — ページ自体が historical record として残る。
ALLOWED_DOMAINS = {__DOMAINS__}
# 許可する frontmatter フィールド（OKF 標準のみ。これ以外は拡張フィールドとしてエラー）
ALLOWED_FIELDS = {"type", "title", "description", "tags"}
# 必須フィールド（非空）。type/tags は型・domain 検査側で扱う。
REQUIRED_FIELDS = ("title", "description")


def parse_frontmatter(text: str):
    """先頭 `---` 行で開き `---` 単独行で閉じる frontmatter を返す。無ければ None。
    閉じ delimiter は行全体が `---` であることを要求する（`---oops` 等の緩い受理を防ぐ）。"""
    if not text.startswith("---\n"):
        return None
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return "\n".join(lines[1:i])
    return None


def get_field(fm: str, key: str):
    """frontmatter から単一行スカラー値を取り出す（前後の引用符は除去）。無ければ None。
    値抽出は行内に限定する（`[ \\t]*` であって `\\s*` ではない。`\\s` は改行を含むため、
    空値のとき次行を誤って巻き込む）。"""
    m = re.search(rf"^{key}:[ \t]*(.*)$", fm, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else None


def filter_gitignored(root: Path, rels: list[str]) -> set[str]:
    """バンドル相対パスのうち gitignore 対象のものを返す。git が無ければ空集合。

    `git check-ignore` は**パターン照合なのでファイルが実在しなくても判定できる**。
    これが要るのは worktree / fresh clone で lint を回したときで、gitignore された
    ページ（`*.local.md`）はそこへコピーされないため、
    それを指す意図的な link が一斉に「切れリンク」として鳴る。主 working tree では
    実体があって普通に解決するので、この関数はそこでは何も落とさない。

    ⚠️ git 呼び出しは `--stdin` でまとめて 1 回。パスごとに呼ぶと件数に比例して遅くなる。
    """
    if not rels:
        return set()
    try:
        r = subprocess.run(["git", "check-ignore", "--stdin"], cwd=root,
                           input="\n".join(rels), capture_output=True, text=True)
    except FileNotFoundError:
        return set()
    # exit 0=1件以上 ignore / 1=0件 / それ以外は異常なので黙って諦める
    if r.returncode not in (0, 1):
        return set()
    return {line.strip() for line in r.stdout.splitlines() if line.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate wiki structure without calling an LLM.")
    parser.add_argument("bundle_root", nargs="?", default="wiki")
    args = parser.parse_args()
    root = Path(args.bundle_root).resolve()
    if not root.is_dir():
        print(f"bundle root が見つからない: {root}")
        return 1

    md_files = sorted(root.rglob("*.md"))
    concept_ids = {f.relative_to(root).with_suffix("").as_posix() for f in md_files
                   if f.name not in RESERVED}
    # link 存在判定用は reserved（index.md 等）も含む全ファイル集合。
    # index.md → 各 domain の index.md（progressive disclosure）が valid なため。
    all_ids = {f.relative_to(root).with_suffix("").as_posix() for f in md_files}
    # bundle の実トップdir（/raw 等のバンドル外 repo-root 参照と区別するため）
    bundle_dirs = {p.name for p in root.iterdir() if p.is_dir()}
    violations: list[str] = []
    external_refs = 0
    broken: list[tuple[str, str, str]] = []  # (link 元, 書かれている link, bundle 相対の解決先)

    for f in md_files:
        rel = f.relative_to(root).as_posix()
        text = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)

        if f.name in RESERVED:
            if f.name == "index.md" and fm is not None:
                violations.append(f"[§6] {rel}: index.md に frontmatter がある")
        else:
            # §9-1 / §9-2 + type/domain enum（プロジェクト規約）
            if fm is None:
                violations.append(f"[§9-1] {rel}: frontmatter が無い/壊れている")
            else:
                m = re.search(r"^type:[ \t]*(.*)$", fm, re.MULTILINE)
                type_val = m.group(1).strip().strip("\"'") if m else ""
                if not type_val:
                    violations.append(f"[§9-2] {rel}: 非空の type が無い")
                elif type_val not in ALLOWED_TYPES:
                    violations.append(
                        f"[type] {rel}: 未定義の type '{type_val}'（許可: {', '.join(sorted(ALLOWED_TYPES))}）"
                    )
                tm = re.search(r"^tags:[ \t]*\[\s*([^,\]\s]+)", fm, re.MULTILINE)
                domain = tm.group(1).strip().strip("\"'") if tm else None
                top_dir = rel.split("/")[0]
                if domain is None:
                    violations.append(f"[domain] {rel}: tags が無い/domain を先頭に持たない")
                elif domain not in ALLOWED_DOMAINS:
                    violations.append(
                        f"[domain] {rel}: 未定義の domain '{domain}'（許可: {', '.join(sorted(ALLOWED_DOMAINS))}）"
                    )
                elif domain != top_dir:
                    violations.append(
                        f"[domain] {rel}: tags 先頭 '{domain}' が配置 dir '{top_dir}' と不一致（domain=dir 規約）"
                    )

                # frontmatter フィールド allowlist（拡張フィールド禁止）+ 重複キー検出
                keylist = re.findall(r"^([A-Za-z_][A-Za-z0-9_-]*):", fm, re.MULTILINE)
                extra = set(keylist) - ALLOWED_FIELDS
                if extra:
                    violations.append(
                        f"[field] {rel}: 許可外フィールド {sorted(extra)}（許可: {', '.join(sorted(ALLOWED_FIELDS))}）"
                    )
                dups = sorted({k for k in keylist if keylist.count(k) > 1})
                if dups:
                    violations.append(f"[field] {rel}: 重複キー {dups}")
                # 必須フィールド（非空）
                for req in REQUIRED_FIELDS:
                    if not get_field(fm, req):
                        violations.append(f"[required] {rel}: 必須フィールド '{req}' が無い/空")
                # description は単文（。は最大1）
                desc = get_field(fm, "description")
                if desc and desc.count("。") > 1:
                    violations.append(f"[description] {rel}: 単文にする（。が {desc.count('。')} 個）")
        # link 検査: bundle 内 .md リンク（index.md=探索の SSOT も対象）。
        # AGENTS.md/CLAUDE.md は例示リンクを含むため除外。外部 URL・bundle 外参照(../../raw 等)は skip。
        # 規約: 内部リンクは file 相対（./foo.md, ../life/bar.md）。先頭 / の bundle-absolute は
        # ビューア（GitHub/VS Code/Obsidian）が fs/web root と解釈し開けないため違反扱い。
        if f.name not in ("AGENTS.md", "CLAUDE.md"):
            rel_dir = posixpath.dirname(rel)
            for link in re.findall(r"\]\(([^)\s]+?\.md)(?:#[^)]*)?\)", text):
                if re.match(r"^[a-z][a-z0-9+.\-]*://", link):
                    continue  # 外部 URL
                if link.startswith("/"):
                    top = link.lstrip("/").split("/", 1)[0]
                    if top not in bundle_dirs:
                        external_refs += 1  # /raw 等 repo-root 参照（bundle 外）
                        continue
                    violations.append(f"[link] {rel}: bundle-absolute 内部リンク -> {link}（file 相対に直す）")
                else:
                    # 相対リンク（規約）: bundle 内に解決するなら存在チェック。
                    resolved = posixpath.normpath(posixpath.join(rel_dir, link))
                    if resolved.startswith(".."):
                        external_refs += 1  # bundle 外（../../raw, ../../AGENTS.md 等）
                        continue
                    if resolved[:-3] not in all_ids:
                        broken.append((rel, link, resolved))

    # 解決できなかった link のうち、gitignore 対象を指すものは違反にしない。
    # 主 working tree では実体があって解決済みなので、ここに落ちるのは worktree /
    # fresh clone で「そもそもコピーされていない」場合＝意図された link である。
    ignored = filter_gitignored(root, sorted({resolved for _, _, resolved in broken}))
    ignored_refs = 0
    for rel, link, resolved in broken:
        if resolved in ignored:
            ignored_refs += 1
        else:
            violations.append(f"[link] {rel}: 切れリンク -> {link}")

    print(f"bundle: {root}")
    print(f"  .md files: {len(md_files)} (concepts: {len(concept_ids)}, "
          f"external refs skipped: {external_refs}, gitignored refs skipped: {ignored_refs})")

    exit_code = 0
    if violations:
        print(f"\n❌ {len(violations)} 件の違反:")
        for v in violations:
            print("  " + v)
        exit_code = 1
    else:
        print("\n✅ OKF §9 conformant + type/domain enum OK / link 切れ無し")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
