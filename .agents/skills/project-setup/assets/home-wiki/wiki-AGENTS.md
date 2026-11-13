# AGENTS.md — wiki/ の schema

wiki/ は LLM が書いて維持する知識ベース。人間は読む側、LLM は書く側。このファイルは wiki/ で作業するときに読む schema で、repo 全体の規約は root の AGENTS.md が持つ。

## 3 層

| 層 | 場所 | 役割 |
| --- | --- | --- |
| raw | `raw/<domain>/`（repo root） | 原本。LLM は読むだけで書き換えない。wiki からは `[link](../../raw/...)` で参照する |
| wiki | `wiki/` | LLM が書いて維持する合成知識 |
| schema | この `wiki/AGENTS.md` | 構造・frontmatter・書き込みの境界・手順 |

## 構造

- **frontmatter** は `type`・`title`・`description`・`tags` の 4 つだけ。他のキーは書かない（`tools/okf-check.ts` がエラーにする）
  - `type` ∈ `concept` / `synthesis` / `person` / `company` / `organization` / `book`。足すときは `tools/okf-check.ts` の `ALLOWED_TYPES` に追記する
  - `title`・`description` は非空。`description` は単文（「。」は最大 1）
  - `tags` は inline 形式（`[a, b]`）で、先頭が domain。domain は配置 dir 名と一致させ、`tools/okf-check.ts` の `ALLOWED_DOMAINS` が正本
  - frontmatter は 1 行スカラーと inline tags だけで書く（checker は YAML を使わず正規表現で読む）
- **dir = domain**。1 domain に 1 dir と `<domain>/index.md` を置き、root の `index.md` の Map から各 domain の index を指す。dir に domain 以外の意味を持たせない
- **index.md** は frontmatter を持たない。各行は `* [title](file.md) - description`
- **リンク**はすべて file 相対（`./foo.md`・`../other/bar.md`・`../../raw/...`）。先頭 `/` は使わない。GFM の表セル内の `|` は `\|` にする
- **節末メタデータ**: `##` 節の末尾に `[source: <出典>; added: YYYY-MM-DD]` を置く。出典の無い節は `[added: YYYY-MM-DD]` だけにし、source を捏造しない。`added` は中身を見直した日で、link の貼り足しでは更新しない

## 書き込みの境界

wiki が持つのは、repo をまたぐ理解・判断・PJ の位置づけ。次のものは書かない。

| 書かないもの | 正本 |
| --- | --- |
| repo の意思決定・採用理由・却下案 | 対象 repo の ADR |
| 再利用する手順 | 対象 repo の skill / reference |
| repo の構造・制約 | 対象 repo の AGENTS.md |
| repo・本番で確かめられる現状（件数・実装状態・PR の進捗） | repo・本番そのもの。wiki には正本の場所だけを置く |
| セッションの経緯・資料の転記 | raw / git の履歴 |

- **決定されたものだけ書く**。判断が変わったら古い記述を並べず、現在の結論で置き換える。変遷は git の履歴が持つ
- **削るのは時系列で、失敗から確定した制約ではない**。却下した案とその理由、試して潰れた対策は現在の結論として残す

## 手順

**引く**: `rg -l '<具体語>' wiki` で候補を絞り、最有力の 1 ページで `rg -n '^#{1,6} |<具体語>' <path>` を使って必要な節だけ読む。外れたら root の `index.md` の Map → domain index の該当行へ進む。dir や更新日で関連性を判断しない。見つからなければ「wiki に該当なし」と答え、捏造しない。

**書く**: 新規ページの前に対象 domain の既存ページを確認する。書いたら次を行う。

1. 実質更新した節の `added` を当日にする
2. `<domain>/index.md` の行を足す・直す
3. 関連する既存ページがあれば file 相対で相互リンクを張る（無ければ孤立のままでよい）
4. `bun tools/okf-check.ts wiki` で検査し、`git diff` で重複・破損・情報漏洩を読み直す

**domain を足す・畳む**: dir と `index.md` を作り、`tools/okf-check.ts` の `ALLOWED_DOMAINS` と root の `index.md` の Map に足す。畳んだ domain は Map から外し、dir と `ALLOWED_DOMAINS` は残す。

**ページを別の home へ移す**: 移した先で inbound link を直し、元の home の参照は移し先の URL に置き換える。元の home の `ALLOWED_DOMAINS` から外すのは、その domain のページが残っていないときだけ。
