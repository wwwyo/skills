# skills

wwwyo が日々の開発で使う agent skill 集です。Claude Code・Codex・pi の plugin / package として配ります。

- `core`: 環境に依存しない汎用 skill（作業の入口の `mode`・PRD・設計・検証・文章・ドキュメントなど）。claude.ai でも使えます
- `design`: UI の見た目・動き・モバイルの挙動・3D を扱う skill（入口の `design-mode`・unslop・design-md・emilkowalski/skills・CloudAI-X/threejs-skills 由来）。claude.ai でも使えます
- `local`: Orca・mise・ローカル CLI など、作者の開発環境を前提にする skill

skill の一覧は [.claude-plugin/marketplace.json](.claude-plugin/marketplace.json) にあります。third-party の skill を含み、取得元は [skills-lock.json](skills-lock.json) に記録しています。

## 使い方

Claude Code:

```bash
claude plugin marketplace add wwwyo/skills
claude plugin install core@wwwyo
claude plugin install design@wwwyo
```

claude.ai では Customize > Plugins から marketplace に `wwwyo/skills` を追加し、`core`・`design` を有効にします。

Codex:

```bash
codex plugin marketplace add wwwyo/skills
codex plugin add core@wwwyo
codex plugin add design@wwwyo
```

pi:

```bash
pi install git:github.com/wwwyo/skills
```

pi は `.agents/skills/` の skill をすべて読み込みます。一部だけ使う場合は `settings.json` の package filter（`skills`）で絞ってください。

## 開発

構成と規約は [AGENTS.md](AGENTS.md) を参照してください。
