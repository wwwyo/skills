# skills

wwwyo の共有 agent skill の正本。Claude Code・Codex・pi へは plugin / package として配り、claude.ai（cloud）には core plugin だけを届ける。開発環境の設定（各 tool への登録・hooks・chezmoi）は [wwwyo/dotfiles](https://github.com/wwwyo/dotfiles) が持つ。

## ディレクトリ構造

```
skills/
├── .agents/
│   ├── skills/<name>/          skill 本体（skillctrl が固定で使う場所）
│   ├── skillctrl/              upstream provenance・受理 hash・intent・評価
│   ├── .codex-plugin/          Codex の local plugin（root = .agents）。生成物
│   └── plugins/marketplace.json  Codex の marketplace。生成物
├── .claude-plugin/marketplace.json  Claude の marketplace。plugin と skill の対応の正本
├── .codex-plugin/plugin.json   Codex の core plugin（root = repo root）。生成物
├── package.json                pi package（pi.skills = ./.agents/skills）
├── skills-lock.json            upstream 登録（npx skills 互換の native lock）
├── scripts/sync-plugin-manifests.py  Claude の marketplace から Codex の定義を生成・検査
├── tests/                      repo 固有の検査（*.test.sh）
└── .github/workflows/          test・skillctrl の gh-aw workflow・Pullfrog
```

## plugin の配布

plugin は `core`（cloud と local の両方。環境に依存しない汎用 skill）と `local`（Orca・dotfiles・mise・ローカル CLI を前提にする skill）の 2 つ。marketplace 名は Claude・Codex とも `wwwyo`。

- skill を足す・plugin を移すときは `.claude-plugin/marketplace.json` の `skills` を編集し、`scripts/sync-plugin-manifests.py` で Codex の定義を再生成する。`tests/plugin-manifests.test.sh` が、全 skill がちょうど 1 つの plugin に載っていることと生成物の一致を検査する
- cloud に載せてよいかで core / local を決める。手元の path・CLI・secret を前提にする skill は local
- Codex は local plugin を cache へコピーし、symlink を落とす。plugin root に skill を symlink で集めず、root からの相対 path で列挙する（core = repo root、local = `.agents`）
- tool が自分で配って自動更新する skill（Orca の `orca-cli`・`orchestration`・`orca-computer-use` 等）はこの repo に置かない（dotfiles の `.agents/skills` で追跡する）。plugin に入れると、tool が書く `~/.agents/skills` の copy と二重に読まれ、tool の更新にも追従しなくなる。手元の方針は dev-env の reference に置く
- skill から同梱の tools を呼ぶ手順は SKILL.md の dir からの相対 path で書く。`~/.agents/skills/...` は存在しない。scheduled task・hook など agent 以外の呼び出し元は canonical checkout（`~/src/github.com/wwwyo/skills`）を指す
- **main への merge は即本番**。手元の pi・Devin と Claude Code の local はこの repo の canonical checkout を直接読む。Codex は `codex plugin add` で cache を更新するまで古い copy を読み、Claude Code の core と claude.ai は marketplace の自動同期で取り込んだ copy を読む（tool ごとの反映は dev-env の skill-plugins を参照）。skill の rename・削除は、それを読む consumer（dotfiles の scheduled task・hook、他 repo の orca.yaml）の切替と同じタイミングで merge する

tool ごとの読み込み方・編集の反映・確認コマンドは [dev-env の skill-plugins](.agents/skills/dev-env/references/skill-plugins.md) を参照する。

## セットアップ

ツールは mise で管理している（CI は PR の base commit の `mise.toml`・`mise.lock` を信頼済みの pin として読む）。

```bash
mise install
skillctrl check                                  # 受理 hash の drift を offline で確認
python3 scripts/sync-plugin-manifests.py         # Codex の plugin 定義を再生成（--check で検査のみ）
for t in tests/*.test.sh .agents/skillctrl/*.test.sh; do bash "$t"; done
claude plugin validate .
```

## Skills 管理

skill の検索・追加・作成・改善・更新・削除は `skillctrl` に統一し、手順は [skillctrl skill](.agents/skills/skillctrl/SKILL.md) と [.agents/skillctrl/README.md](.agents/skillctrl/README.md) に従う。CLI は cwd の Git repo を対象にするので、この repo の worktree で実行する。skill の追加・削除をしたら `.claude-plugin/marketplace.json` も同じ変更で更新する。

- upstream 管理 skill を意図的に変えるときは、保ちたい振る舞いの理由を `.agents/skillctrl/intents/<name>.md` に書き、検証後に `skillctrl record <name>` で受理する。意図ファイルを差分や patch の正本にしない
- 手書き skill（`memo` `wiki` `project-setup` 等）は upstream lock に載らず、受理 hash の対象外
- PR では [skillctrl](.github/workflows/skillctrl.md) が hash drift のときだけ AI に intent 適合を審査させる。土曜 09:00 JST の [skillctrl-update](.github/workflows/skillctrl-update.md) が upstream 更新を取り込み draft PR を作る。AI engine は pi / OpenCode Go を固定し、repo secret `OPENCODE_API_KEY` を使う
- 独立 skill として残すかの基準は「その skill だけを目的に起動する場面があるか」。無ければ既存 skill の reference か節にする
- 運用ルールの記載先は、情報の発生源（不具合の根拠・制約の由来）と適用時（操作を行う skill）で分ける。発生源にだけ書くと使う側が見ず、両方に全文書くと drift する
- skill・reference の rename・移動・削除では、path だけでなく link の表示名・anchor も repo 全体と dotfiles・wwwyo/me を grep して残存参照を消す
- gh-aw の `.md` を変えたら `gh aw compile` の生成物と、`uses:` が変われば `.github/workflows/actions.lock`（`gh-actions-lock --no-narrow`）も同じ変更に含める（[gh-aw](.agents/skills/dev-env/references/gh-aw.md)）

## 他 repo・他セッションから触るとき

main から worktree を切って作業し、PR で入れる。canonical checkout は pi・Devin・Claude Code の local が直接読む本番なので、そこで branch を切り替えたり未 merge の変更を置いたりしない。

## Pullfrog の個別設定

この repo の Pullfrog 設定は [`.github/pullfrog.config.sh`](.github/pullfrog.config.sh) が正本。public repo なので初回レビューと追加コミットの再レビューを自動で行い、手動でも `@pullfrog` で依頼できる。model・effort は org 共通設定（dotfiles の `.github/pullfrog.org.config.sh`）を継承する。
