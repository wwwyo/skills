# skill の plugin 配布（Claude・Codex・pi・Devin）

共有 skill の正本は `wwwyo/skills` repo の `.agents/skills/`（canonical checkout は `~/src/github.com/wwwyo/skills`）。各 tool へは plugin / package として配り、`~/.agents/skills`・`~/.claude/skills` への symlink では配らない。repo 側の layout と manifest の生成は wwwyo/skills の `AGENTS.md` が正本。ここには tool ごとの読み込み方の差を置く（2026-11-10 に Claude Code 2.1.316・codex-cli 0.166.0・pi 1.4.0 で確認）。

| tool | 登録 | 読む場所 | 編集の反映 |
| --- | --- | --- | --- |
| Claude Code | `extraKnownMarketplaces` に directory source、`enabledPlugins` に `core@wwwyo`・`local@wwwyo` | 元フォルダを直接読む（`claude plugin list --json` の `readFromFolder`）。cache にも copy は作られるが使わない | 次の session 開始か `/reload-plugins`。commit も `plugin update` も要らない |
| Codex | `[marketplaces.wwwyo]`（local source）と `[plugins."core@wwwyo"]` 等 | `~/.codex/plugins/cache/wwwyo/<plugin>/<version>/` の copy | `codex plugin add <plugin>@wwwyo` を再実行するまで反映されない（同じ version でも上書きされる）。CLI の起動（`codex debug prompt-input`）では cache は更新されなかった。desktop app の再起動で更新されるかは未確認 |
| pi | `settings.json` の `packages` にローカルパス | その場で読む（copy しない）。未 commit の編集も見える | `/reload` か次の起動 |
| Devin | plugin を使わず `~/.config/devin/skills` を `.agents/skills` へ dir link | link 先を直接読む | 次の起動 |

- **Codex の cache copy は symlink を落とす**。plugin root の外を指すものも中を指すものも消えるため、skill を symlink で plugin root に集める layout は Codex では空になる。plugin root は実ファイルを含む dir にし、`.codex-plugin/plugin.json` の `skills` に配列で skill dir を 1 つずつ列挙する（`skills` は文字列だけでなく配列も受け付け、dir 単位の指定も効く）。2 つの plugin は root を分ける必要があり、core = repo root、local = `.agents` にしている
- **Codex の core root は repo root なので `.git` も cache に copy される**。容量の問題が出たら plugin root の切り方を見直す
- **Codex で読まれた skill の確認**は `codex debug prompt-input hi` の出力を `core:<name>` で grep する（API に届かなくても prompt は出力される）。Claude は `claude plugin details core@wwwyo`、pi は `pi --mode rpc --offline --no-session` に `{"type":"get_commands"}` を送ると `skill:<name>` と読み込み元 path が返る
- **plugin skill は名前空間付きになる**（Claude・Codex は `core:pr`）。pi は名前空間を付けない
- **`.agents/skills/computer-use` は skillctrl の alias symlink**（upstream 側の名前のまま `update` するため）で、manifest には載せない。Codex は copy で落とし、Claude・pi では実体の `orca-computer-use` と重複する
- **claude.ai（cloud）には core だけを入れる**。Customize > Plugins で marketplace `wwwyo/skills` を追加し core を有効にする。cloud の Projects スレッドは `~/.agents` も repo の `.claude/skills` も読まず、アカウントの plugin だけが届く。アカウントの plugin は local の Claude Code にも `core@synced` として同期されるため、local では `"core@synced": false` で無効にし、directory marketplace の `core@wwwyo` と重複させない
- skill から自分の tools を呼ぶときは `~/.agents/skills/...` の絶対 path を書かない。cloud・Codex cache では存在しない。agent が読む手順は SKILL.md の dir からの相対 path で書き、scheduled task・hook など agent 以外の呼び出し元は canonical checkout（`~/src/github.com/wwwyo/skills/.agents/skills/...`）を指す
