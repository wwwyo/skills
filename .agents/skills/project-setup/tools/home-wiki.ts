#!/usr/bin/env bun
/**
 * home repo に memory（LLM wiki）の骨組みを置く・domain を足す（依存なし。Bun で実行する）。
 *
 * 使い方:
 *   bun home-wiki.ts <home-dir> --domain <name>[=<説明>] [--domain ...] [--dry-run]
 *
 * 置くもの（既存の file は上書きしない）:
 *   raw/.gitkeep, wiki/AGENTS.md（schema）, wiki/CLAUDE.md, wiki/index.md（Map）,
 *   wiki/<domain>/index.md, tools/okf-check.ts（検査）, root AGENTS.md の「メモリ（wiki）」節
 * 既存の wiki/index.md と tools/okf-check.ts には、足りない domain だけを追記する。
 * 最後に bun tools/okf-check.ts wiki を実行し、結果を stdout に 1 行の JSON で返す。
 * 検査が通らなければ exit 1、引数の誤りは exit 2。
 */
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { parseArgs } from "node:util";

const ASSETS = join(import.meta.dir, "..", "assets", "home-wiki");
const DOMAIN_RE = /^[a-z0-9][a-z0-9-]*$/;
const DOMAINS_LINE = /^const ALLOWED_DOMAINS = new Set\(\[([^\]]*)\]\);/m;
const MEMORY_HEADING = "## メモリ（wiki）";

const fail = (message: string, code = 2): never => {
  console.error(JSON.stringify({ error: message }));
  process.exit(code);
};
const asset = (name: string) => readFileSync(join(ASSETS, name), "utf8");
const mapRow = (name: string, desc: string) => `* [${name}](./${name}/index.md)` + (desc ? ` - ${desc}` : "");
const domainsLiteral = (names: Iterable<string>) => [...new Set(names)].sort().map((n) => `"${n}"`).join(", ");

const { values, positionals } = parseArgs({
  args: Bun.argv.slice(2),
  options: { domain: { type: "string", multiple: true }, "dry-run": { type: "boolean", default: false } },
  allowPositionals: true,
});
if (positionals.length !== 1 || !values.domain?.length) {
  fail("usage: home-wiki.ts <home-dir> --domain <name>[=<説明>] [--domain ...] [--dry-run]");
}
const home = resolve(positionals[0]);
const dryRun = values["dry-run"]!;
const domains = values.domain!.map((raw) => {
  const i = raw.indexOf("=");
  const name = (i < 0 ? raw : raw.slice(0, i)).trim();
  if (!DOMAIN_RE.test(name)) fail(`invalid domain: '${name}'（小文字英数字と - のみ）`);
  return { name, desc: i < 0 ? "" : raw.slice(i + 1).trim() };
});
const names = domains.map((d) => d.name);
if (!existsSync(join(home, ".git"))) fail(`not a git repository: ${home}`);

const wiki = join(home, "wiki");
const checker = join(home, "tools", "okf-check.ts");
// 既存 checker の domain 行を読めないなら、何も書く前に止める（途中まで書いた状態を残さない）
if (existsSync(checker) && !DOMAINS_LINE.test(readFileSync(checker, "utf8"))) {
  fail(`${checker}: const ALLOWED_DOMAINS = new Set([...]); の形の定義が見つからない。手で domain を足すかこの形に戻してから再実行する`);
}

const created: string[] = [];
const updated: string[] = [];
function write(path: string, text: string, isNew: boolean) {
  (isNew ? created : updated).push(relative(home, path));
  if (dryRun) return;
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, text);
}
const ensureFile = (path: string, text: string) => existsSync(path) || write(path, text, true);

ensureFile(join(home, "raw", ".gitkeep"), "");
ensureFile(join(wiki, "AGENTS.md"), asset("wiki-AGENTS.md"));
ensureFile(join(wiki, "CLAUDE.md"), "read @AGENTS.md\n");

// Map: 無ければ雛形から作り、あれば Map 節の最後の行頭 `* [` の直後へ足りない domain を足す
const indexPath = join(wiki, "index.md");
if (!existsSync(indexPath)) {
  write(indexPath, asset("index.md").replace("__MAP__", domains.map((d) => mapRow(d.name, d.desc)).join("\n")), true);
} else {
  const text = readFileSync(indexPath, "utf8");
  const missing = domains.filter((d) => !text.includes(`](./${d.name}/index.md)`));
  if (missing.length) {
    const lines = text.split("\n");
    let start = lines.indexOf("## Map");
    if (start < 0) {
      lines.push("", "## Map", "");
      start = lines.length - 2;
    }
    let insertAt = start + 1;
    for (let i = start + 1; i < lines.length && !lines[i].startsWith("## "); i++) {
      if (lines[i].startsWith("* [")) insertAt = i + 1;
    }
    if (insertAt === start + 1) lines.splice(insertAt++, 0, "");
    lines.splice(insertAt, 0, ...missing.map((d) => mapRow(d.name, d.desc)));
    write(indexPath, lines.join("\n"), false);
  }
}

for (const d of domains) ensureFile(join(wiki, d.name, "index.md"), `${d.desc || d.name}\n`);

if (!existsSync(checker)) {
  write(checker, asset("okf-check.ts").replace("__DOMAINS__", domainsLiteral(names)), true);
  if (!dryRun) chmodSync(checker, 0o755);
} else {
  const text = readFileSync(checker, "utf8");
  const m = text.match(DOMAINS_LINE)!;
  const current = [...m[1].matchAll(/"([^"]+)"/g)].map((x) => x[1]);
  if (!names.every((n) => current.includes(n))) {
    const line = `const ALLOWED_DOMAINS = new Set([${domainsLiteral([...current, ...names])}]);`;
    write(checker, text.slice(0, m.index) + line + text.slice(m.index! + m[0].length), false);
  }
}

const agentsPath = join(home, "AGENTS.md");
const section = asset("agents-memory.md");
if (!existsSync(agentsPath)) write(agentsPath, `# AGENTS.md\n\n${section}`, true);
else {
  const text = readFileSync(agentsPath, "utf8");
  if (!text.includes(MEMORY_HEADING)) write(agentsPath, `${text.replace(/\n+$/, "")}\n\n${section}`, false);
}

const result: Record<string, unknown> = { home, dry_run: dryRun, created, updated };
let code = 0;
if (!dryRun) {
  const r = Bun.spawnSync([process.execPath, "tools/okf-check.ts", "wiki"], { cwd: home });
  result.check = { ok: r.exitCode === 0, output: r.stdout.toString().trim() };
  code = r.exitCode === 0 ? 0 : 1;
}
console.log(JSON.stringify(result));
process.exit(code);
