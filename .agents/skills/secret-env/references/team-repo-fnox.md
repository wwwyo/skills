# team 共有 repo の secret（fnox + age）

手元で使う secret を team repo に置くときの規約と落とし穴。実例は fudoki-hensansitu/fudoki の `fnox.toml` と AGENTS.md の「secret」。

## 置き場所の分け方

- 手元で使う secret（agent・script が叩く API key など）: repo root の `fnox.toml` に age で暗号化して commit する。値は `recipients` の公開鍵の全員が自分の秘密鍵で開ける
- secret ではない値（Cloudflare の account ID など）: `mise.toml` の `[env]` に平文で置く。暗号化しても復号の手間が増えるだけ
- CI・deploy の token: GitHub secret のまま。本番の Worker の secret は Cloudflare に置く。CI を fnox 経由にすると `FNOX_AGE_KEY` 1 本で repo の secret が全部開くので、漏れたときの範囲が広がる。deploy token を `fnox.toml` に入れると recipients 全員（と抜けた人）が本番に deploy できる
- public repo では暗号文が誰でも見られる。鍵が漏れたら git 履歴の暗号文も開くので、そのときは値を rotate する

## 鍵の分け方

- 鍵は repo 専用に作る。個人の age 鍵（global の mise を開ける `MISE_AGE_KEY`）を team repo の recipients に入れない。repo の鍵が漏れても global は開かず、global の鍵が漏れても repo は開かない
- 秘密鍵は Keychain の service `fnox-<repo>`、account `age-key` に置き、`fnox.toml` の `identity` で読む。shell に `FNOX_AGE_KEY` を export しない（export すると `identity` より優先され、全 repo の fnox に同じ鍵が渡る）

```toml
default_provider = "age"
env = "exec"   # fnox activate の shell には export せず、fnox exec の command にだけ渡す

[providers.keychain]
type = "keychain"
service = "fnox-<repo>"

[providers.age]
type = "age"
recipients = [
  "age1...", # yuito
  "age1...", # ai（cloud agent 用。cloud 環境の FNOX_AGE_KEY）
]
identity = { provider = "keychain", value = "age-key" }
```

- 鍵の作成（macOS。repo の中で実行し、公開鍵だけが表示される）。既に項目があれば作らずに止める（上書きすると既存の暗号文を開けなくなる）。秘密鍵を `security add-generic-password -w <値>` に渡すと process 一覧に見えるので、一時 dir の fnox 設定から keychain provider に stdin で書く。`age-keygen -o` は既存ファイルに書かないので `mktemp -d` の中に作る:

```sh
s=fnox-REPO a=age-key F=$(mise which fnox)  # REPO を repo 名に変える
if security find-generic-password -s "$s" -a "$a" >/dev/null 2>&1; then echo "exists: $s/$a"; else
  d=$(mktemp -d) && age-keygen -o "$d/k" 2>/dev/null && age-keygen -y "$d/k" &&
  printf '[providers.keychain]\ntype = "keychain"\nservice = "%s"\n' "$s" > "$d/fnox.toml" &&
  (cd "$d" && grep '^AGE-SECRET-KEY' k | "$F" set K --provider keychain --key-name "$a" >/dev/null); rm -rf "$d"
fi
```

- repo の中で `fnox set X --provider keychain` を実行すると repo の `fnox.toml` の `[secrets]` に記録が増え、以後 `fnox exec` の env に秘密鍵が入る。上のように一時 dir の設定で書く
- AI agent（cloud 環境）・CI には専用の鍵を 1 本ずつ作って recipients に足し、秘密鍵を環境変数 `FNOX_AGE_KEY` で渡す。`FNOX_AGE_KEY` は `identity` より優先されるので、Keychain の無い Linux でも開ける。手元の Keychain には別 account（`age-key-ai` など）で保管し、`security find-generic-password -s fnox-<repo> -a age-key-ai -w | tr -d '\n' | pbcopy` で画面・履歴に出さずに貼る
- cloud 環境に fnox を入れるときは mise を版固定で入れて `mise.toml` の pin に従わせる（`curl -fsSL https://mise.run | MISE_VERSION=vX.Y.Z sh` → `mise trust --yes && mise install`）。setup script に fnox の版・sha を別に書くと二重管理になる

## 使い方

- 実行は `fnox exec --if-missing error -- <command>`。`--if-missing error` が無いと、復号できない値は警告だけで env に入らないまま command が走る
- `fnox get`・`fnox export`・`printenv` で値を画面や log に出さない。値の登録は `fnox set <KEY>` の hidden prompt か stdin（引数は shell 履歴に残る）。既存の値を移すときは、取り出しの失敗で空の値を書かないよう、取り出して確かめてから渡す: `v=$(mise -C ~ exec -- printenv KEY) && [ -n "$v" ] && printf %s "$v" | fnox set KEY; unset v`
- 移行の照合は値を出さず、`printf %s "$KEY" | shasum -a 256 | cut -c1-8` を両側で比べる

## メンバー・agent の増減

- 足す: その人（agent）の公開鍵を recipients に 1 行足し、鍵を持つ人が `fnox reencrypt -p age` で暗号文を作り直す（新しい宛先の行は file key を知らないと作れない）。`fnox reencrypt` は今の profile だけを作り直すので、profile を分けている repo では `-P <profile>` で profile ごとに繰り返す
- 外す: 行を消して `fnox reencrypt -p age`、agent なら環境変数 `FNOX_AGE_KEY` も消す。git 履歴の古い暗号文はまだ開けるので、値そのものを rotate する
- Keychain の項目名を変えたときは `fnox.toml` の `service` / `value` を直すだけで、暗号文は作り直さない（暗号文には鍵の置き場所の情報が無い）

## fnox の落とし穴（1.46.0 時点）

- ドキュメントの名前付き recipients（`[providers.age.recipients]` の表）は TOML の型エラーで読めない。配列 + 行末コメントで名前を残す。ドキュメントは最新版基準なので、使う版で試してから書く
- mise の fnox 連携（`[secrets.fnox]`）は mise の task（`secrets = [...]`）か `--secrets` 付きの実行にしか値を渡さない。bun・npm script から呼ぶ repo では `fnox exec --` を使う
- `fnox exec` を mise の shim 経由で呼ぶとき、検証で `HOME` を変えると mise が落ちる。fnox の実体（`mise which fnox`）を直接呼ぶ
