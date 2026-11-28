#!/usr/bin/env bun
/**
 * wiki の構造を検査する（依存なし。Bun で実行する）。
 *
 * 使い方: bun tools/okf-check.ts [bundle_root]  (default: wiki)
 *
 * 検査内容:
 *   [frontmatter] 予約名以外の全 .md が frontmatter を持つ
 *   [type]        type が ALLOWED_TYPES に含まれる
 *   [domain]      tags 先頭が ALLOWED_DOMAINS に含まれ、配置 dir 名と一致する
 *   [field]       frontmatter のキーが ALLOWED_FIELDS だけで、重複しない
 *   [required]    title / description が非空
 *   [description] description が単文（。は最大 1）
 *   [index]       index.md は frontmatter を持たない
 *   [link]        bundle 内の相対 link が実在し、先頭 / の bundle-absolute link を使っていない
 *
 * frontmatter は「1 行スカラー + inline tags（`[a, b]`）」の限定文法を前提に正規表現で読む。
 * domain の追加はこの file の ALLOWED_DOMAINS を直接編集する。違反があれば exit 1。
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, posix, relative, resolve, sep } from "node:path";

const RESERVED = new Set(["index.md", "AGENTS.md", "CLAUDE.md"]);
const ALLOWED_TYPES = new Set(["concept", "synthesis", "person", "company", "organization", "book"]);
// domain（tags 先頭 = 配置 dir 名）。撤退・完了した domain も削除しない。
const ALLOWED_DOMAINS = new Set([__DOMAINS__]);
const ALLOWED_FIELDS = new Set(["type", "title", "description", "tags"]);
const REQUIRED_FIELDS = ["title", "description"];

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return walk(p);
    return name.endsWith(".md") ? [p] : [];
  });
}

/** 先頭 `---` 行で開き `---` 単独行で閉じる frontmatter を返す。無ければ null。 */
function parseFrontmatter(text: string): string | null {
  if (!text.startsWith("---\n")) return null;
  const lines = text.split("\n");
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trimEnd() === "---") return lines.slice(1, i).join("\n");
  }
  return null;
}

/** 1 行スカラーの値（前後の引用符は除く）。空値のとき次行を巻き込まないよう行内に限る。 */
function getField(fm: string, key: string): string | null {
  const m = fm.match(new RegExp(`^${key}:[ \\t]*(.*)$`, "m"));
  return m ? m[1].trim().replace(/^["']|["']$/g, "") : null;
}

const root = resolve(process.argv[2] ?? "wiki");
try {
  if (!statSync(root).isDirectory()) throw new Error();
} catch {
  console.log(`bundle root が見つからない: ${root}`);
  process.exit(1);
}

const files = walk(root).sort();
const rel = (f: string) => relative(root, f).split(sep).join("/");
const allIds = new Set(files.map((f) => rel(f).replace(/\.md$/, "")));
const bundleDirs = new Set(readdirSync(root).filter((n) => statSync(join(root, n)).isDirectory()));
const violations: string[] = [];
let concepts = 0;
let externalRefs = 0;

for (const f of files) {
  const r = rel(f);
  const name = r.split("/").pop()!;
  const text = readFileSync(f, "utf8");
  const fm = parseFrontmatter(text);

  if (RESERVED.has(name)) {
    if (name === "index.md" && fm !== null) violations.push(`[index] ${r}: index.md に frontmatter がある`);
  } else {
    concepts++;
    if (fm === null) {
      violations.push(`[frontmatter] ${r}: frontmatter が無い/壊れている`);
    } else {
      const type = getField(fm, "type") ?? "";
      if (!type) violations.push(`[type] ${r}: 非空の type が無い`);
      else if (!ALLOWED_TYPES.has(type))
        violations.push(`[type] ${r}: 未定義の type '${type}'（許可: ${[...ALLOWED_TYPES].sort().join(", ")}）`);

      const tm = fm.match(/^tags:[ \t]*\[\s*([^,\]\s]+)/m);
      const domain = tm ? tm[1].replace(/^["']|["']$/g, "") : null;
      const topDir = r.split("/")[0];
      if (domain === null) violations.push(`[domain] ${r}: tags が無い/domain を先頭に持たない`);
      else if (!ALLOWED_DOMAINS.has(domain))
        violations.push(`[domain] ${r}: 未定義の domain '${domain}'（許可: ${[...ALLOWED_DOMAINS].sort().join(", ")}）`);
      else if (domain !== topDir)
        violations.push(`[domain] ${r}: tags 先頭 '${domain}' が配置 dir '${topDir}' と不一致`);

      const keys = [...fm.matchAll(/^([A-Za-z_][A-Za-z0-9_-]*):/gm)].map((m) => m[1]);
      const extra = [...new Set(keys.filter((k) => !ALLOWED_FIELDS.has(k)))].sort();
      if (extra.length) violations.push(`[field] ${r}: 許可外フィールド ${JSON.stringify(extra)}`);
      const dups = [...new Set(keys.filter((k, i) => keys.indexOf(k) !== i))].sort();
      if (dups.length) violations.push(`[field] ${r}: 重複キー ${JSON.stringify(dups)}`);

      for (const req of REQUIRED_FIELDS) {
        if (!getField(fm, req)) violations.push(`[required] ${r}: 必須フィールド '${req}' が無い/空`);
      }
      const desc = getField(fm, "description");
      const periods = desc ? (desc.match(/。/g) ?? []).length : 0;
      if (periods > 1) violations.push(`[description] ${r}: 単文にする（。が ${periods} 個）`);
    }
  }

  // AGENTS.md / CLAUDE.md は例示 link を含むので検査しない。外部 URL と bundle 外参照は数えるだけ
  if (name === "AGENTS.md" || name === "CLAUDE.md") continue;
  const dir = posix.dirname(r);
  for (const m of text.matchAll(/\]\(([^)\s]+?\.md)(?:#[^)]*)?\)/g)) {
    const link = m[1];
    if (/^[a-z][a-z0-9+.\-]*:\/\//.test(link)) continue;
    if (link.startsWith("/")) {
      if (!bundleDirs.has(link.slice(1).split("/")[0])) externalRefs++;
      else violations.push(`[link] ${r}: bundle-absolute 内部リンク -> ${link}（file 相対に直す）`);
      continue;
    }
    const target = posix.normalize(posix.join(dir, link));
    if (target.startsWith("..")) {
      externalRefs++;
      continue;
    }
    if (!allIds.has(target.replace(/\.md$/, ""))) violations.push(`[link] ${r}: 切れリンク -> ${link}`);
  }
}

console.log(`bundle: ${root}`);
console.log(`  .md files: ${files.length} (concepts: ${concepts}, external refs skipped: ${externalRefs})`);
if (violations.length) {
  console.log(`\n❌ ${violations.length} 件の違反:`);
  for (const v of violations) console.log(`  ${v}`);
  process.exit(1);
}
console.log("\n✅ frontmatter・type・domain OK / link 切れ無し");
