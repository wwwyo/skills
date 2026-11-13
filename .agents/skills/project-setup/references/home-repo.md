# Home repo のセットアップ

home repo は、agent を起動する起点にする 1 つの git repo。repo をまたぐ skill・tool・AGENTS.md・共有 doc を持ち、AGENTS.md の pointer から他の repo を開く・無ければ clone する（出典: [The Home Repo Pattern](https://www.aihero.dev/the-home-repo-pattern)）。

1 repo で起動した agent はその repo しか見えず、skill や agent の設定が repo ごとに重複し、repo をまたぐ計画も立てにくい。home に集めると、steering file と tooling の置き場・agent の起動場所が 1 つになり、複数 repo への一括変更を 1 session で扱える。monorepo にできるならそちらを選ぶ。public と private が混ざる、チームが monorepo を採らないときの代替が home repo。

## 置くもの・置かないもの

| home に置く | 各 repo に残す |
| --- | --- |
| repo をまたいで使う skill・tool（外部サービスへ繋ぐ CLI と、その環境変数など） | その repo だけの AGENTS.md・build/test コマンド・docs |
| AGENTS.md（導入と他 repo への pointer） | コード・履歴・remote・issue tracker |
| 共有 doc（コーディング規約・Glossary・全体に効く決定。最初に共有するならコーディング規約） | |
| wiki（下の節） | |

## pointer の書式

AGENTS.md の「他 repo」節に 1 repo 1 行で書く。harness が別の file（Claude Code の CLAUDE.md）を読むなら、そこを AGENTS.md への 1 行の転送にする。

```
<name>（<何か>）: <local path>。無ければ <remote> から clone。
```

必要なら「変更前にその repo の AGENTS.md を読む」「checkout が古ければ pull する」などの hint を足す。約 20 repo までは 1 行ずつ。それを超えたら領域ごとの file に分け、AGENTS.md からはその file を指す。

各 repo は 1 度だけ clone し、機能ごとにその clone から worktree を切ると、複数の agent が同じ repo を並行して触れる。

## wiki

repo をまたぐ理解・判断を session をまたいで残す場所として、home に [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 型の `wiki/` を置く。原本は `raw/`（LLM は読むだけ）、LLM が書いて維持する markdown が `wiki/`、その schema が `wiki/AGENTS.md`。

骨組みは [tools/home-wiki.ts](../tools/home-wiki.ts)（Bun で動く。先に `setup.sh tools bun` で mise に入れる）が置く。home の root と domain（開発・事業・マーケティングなど、home の中の境界）を渡す。

```bash
bun <skill-dir>/tools/home-wiki.ts <home-dir> --domain product="開発" --domain business="事業" --domain marketing="マーケティング"
```

- 置くもの: `raw/`、`wiki/AGENTS.md`（schema の雛形）、`wiki/index.md`（Map）、`wiki/<domain>/index.md`、`tools/okf-check.ts`（frontmatter・domain・link 切れの検査）、root `AGENTS.md` の「メモリ（wiki）」節。既存の file は上書きせず、再実行で domain を足せる。最後に検査を回して結果を JSON で返す（`--dry-run` で書く file だけを確認できる）
- 雛形は [assets/home-wiki/](../assets/home-wiki/)。置いた後は home 側が正本で、schema も home で直接直す
- 既存の home で育った PJ を独立させるときは、新しい home で `home-wiki.ts` を回してページと `raw/` を移し、元の home の inbound link を移し先の URL に置き換える。移し先の domain は PJ 名ではなく、その中の境界で切り直す

## 手順

**計画をユーザーが承認するまで何も変更しない。** 事実は自分で調べ、ユーザーには判断だけを聞く。`.env` などの secret ファイルは読まない。push はユーザーが決める。

1. **repo の棚卸し**: 対象の親 dir 配下の git repo を列挙し、path・remote・visibility・最終 commit 日を表にする。どれを含めるか、home をどこに置くか（既定は他 repo と並べた新しい private repo）、個人用かチーム共有か、harness がどの file を読むかを決める
2. **共有物の棚卸し**: 各 repo の skill・AGENTS.md・CLAUDE.md・agent 向け doc を列挙し、shared（home へ）・duplicate（差分を見て最新を 1 つ残す）・repo-specific（残す）・installed（公開元から入れたもの）に分類する
3. **計画の合意**: 項目ごとの現在地と移動先の表と、AGENTS.md の草案を出す。判断は番号付きの回にまとめ、各回に推奨を添える
4. **適用**: home repo と AGENTS.md を作り、共有物を copy する（skill は dir ごと）。`home-wiki.ts` で wiki を置き、home で commit する。子 repo から移した copy は、子 repo ごとに新しいローカル branch で消す

## 新しい PJ を立てたとき

通常ワークフローで立ち上げた repo は、その repo を扱う home の「他 repo」節に 1 行足す。
