# Home repo のセットアップ

home repo は、agent session を起動する起点になる 1 つの repo。共有の steering file（AGENTS.md・共有 doc）、他の repo への pointer、session をまたぐ memory を持ち、agent はそこから必要な repo を開く・無ければ clone する（出典: [The Home Repo Pattern](https://www.aihero.dev/the-home-repo-pattern)）。

1 repo で起動した agent はその repo しか見えない。複数 repo にまたがる機能の設計や一括変更を、home から 1 session で扱えるようにするのが目的。monorepo にできるならそちらを選ぶ。public と private が混ざる・チームが monorepo を採らないときの代替が home repo。

個人の home は `wwwyo/me`。新しく作るのは、チーム・org 単位の home を立てるとき。

## 置くもの・置かないもの

| home に置く | 各 repo に残す |
| --- | --- |
| 他 repo への pointer（AGENTS.md の節） | その repo 固有の AGENTS.md・build/test コマンド |
| repo をまたぐ共有 doc（コーディング規約・Glossary・全体に効く決定） | その repo だけの docs・ADR |
| memory（LLM wiki。下の節） | その repo の決定（ADR）・手順（skill） |
| 必要なら home 自身の tools（外部サービスへ繋ぐ CLI など） | コード・履歴・remote・issue tracker |

skill は home に copy しない。共有 skill の正本は wwwyo/skills で、plugin として各 tool に配っている（チームの home なら、そのチームの skill repo か marketplace を pointer で指す）。棚卸しで見つかった skill は「installed」に分類し、home へ移さない。

## pointer の書式

home の AGENTS.md に「他 repo」節を作り、1 repo 1 行で書く。CLAUDE.md は `read @AGENTS.md` の転送役のまま。

```
<name>（<何か>）: <local path>。無ければ <remote> から clone。<必要なら「変更前にその repo の AGENTS.md を読む」等>
```

- local path は ghq の規約（`~/src/github.com/<owner>/<repo>`）で書き、clone は `ghq get <owner>/<repo>`
- 目安は 20 repo 程度まで 1 行ずつ。それを超えたら領域（PJ・事業）ごとの file に分け、AGENTS.md からはその file を指す（progressive disclosure）。me は約 15 repo なので root `AGENTS.md` の「他 repo」に直接並べている
- 作業は各 repo の clone から worktree を切って行い、複数 agent が同じ repo を並行して触れるようにする。各 repo の「他 repo から触るとき」の規約があればそれに従う

## memory（LLM wiki）

session は終われば文脈を失うので、次の session が聞き直さずに済む知識を home に持たせる。形は [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) の 3 層にする。

| 層 | 置き場 | 役割 |
| --- | --- | --- |
| raw | `raw/`（日々の記録を残すなら `daily/` も） | 原本。LLM は読むだけで書き換えない |
| wiki | `wiki/` | LLM が書いて維持する markdown。`wiki/index.md` を router にし、domain ごとの dir に分ける |
| schema | `wiki/AGENTS.md` | wiki の構造・frontmatter・書き込みの境界・ingest / query / lint の手順 |

骨組みは [tools/home_wiki.py](../tools/home_wiki.py) が置く。home の root を渡し、memory の domain を `--domain <name>=<Map の説明>` で並べる（`--dry-run` で書く file だけを確認できる）。

```bash
python3 <skill-dir>/tools/home_wiki.py <home-dir> --domain fudoki="風土記の事業・顧客・制度の理解" --domain municipality="自治体の業務・制度"
```

- 置くもの: `raw/`、`wiki/AGENTS.md`（schema の雛形）、`wiki/index.md`（Map）、`wiki/<domain>/index.md`、`tools/okf_check.py`（frontmatter・domain・link 切れの検査）、`.gitignore` の `*.local.*`、root `AGENTS.md` の「メモリ（wiki）」節。既存の file は上書きせず、既存の Map と `okf_check.py` には足りない domain だけを足す。最後に検査を回し、結果を JSON で返す
- 雛形は [assets/home-wiki/](../assets/home-wiki/)。置いた後は home 側が正本で、schema の調整・domain の追加は home で直接編集する（再実行で domain を足すこともできる）
- schema の雛形は書き込みの境界を最初から持つ。wiki が持つのは repo をまたぐ理解・判断・PJ の位置づけで、repo の決定は各 repo の ADR、手順は skill、repo で確かめられる現状（実装状態・件数）は書かない。境界が無いと ADR や repo の内容の写しが溜まり、古い値が事実として引かれる
- 個人の home（`wwwyo/me`）は同じ構成に router（`tools/wiki_route.py`）と `wiki-lint` skill を足して運用している。雛形の schema は me の `wiki/AGENTS.md` から個人用の規約を除いたもの
- 既存の home から育った PJ を独立させるときは、新しい home で `home_wiki.py` を回してから domain の dir と `raw/` を移し、元の home の inbound link を移し先の URL に置き換えて domain を Map から外す

## 手順

**計画をユーザーが承認するまで何も変更しない。** `.env` などの secret ファイルは読まない。

1. **repo の棚卸し**: 対象の親 dir（例: `~/src/github.com/<owner>`）配下の git repo を列挙し、path・remote・visibility・最終 commit 日を表にする。どれを含めるか、home をどこに置くか（既定は他 repo と並べた新しい private repo）、個人用かチーム共有かをユーザーに確認する
2. **共有物の棚卸し**: 各 repo の skill・AGENTS.md・CLAUDE.md・agent 向け doc を列挙し、shared（home へ）・duplicate（最新を 1 つ残す）・repo-specific（残す）・installed（plugin・tool が配るので触らない）に分類する
3. **計画の合意**: 項目ごとの現在地と移動先の表、「他 repo」節を含む home の AGENTS.md 草案、memory の domain 一覧と schema 草案を出し、未決事項を詰める
4. **適用**: home repo を作り（新規なら通常ワークフローのステップ 1・10 で repo 作成・publish）、AGENTS.md・共有物を置き、`tools/home_wiki.py` で memory の骨組みを置いて commit する。子 repo から移した copy の削除は、子 repo ごとに新しい branch で行い PR にする

## 新しい PJ を立てたとき

通常ワークフローで立ち上げた repo は、home の pointer に載せる。個人 PJ（owner `wwwyo`）はステップ 12 で `wwwyo/me` の「他 repo」に足す。チームの home がある PJ は、その home の「他 repo」節に 1 行足す。
