# tools/

`design.md`（repo root の視覚正本）を読む決定論チェックの正本。フォーマットを定義する design-md skill が持つ。product-design 型 skill や agent はここを**参照して直接実行する — コピーしない**（コピーは drift する。product-design skill が未作成の repo でも design-md だけで検証できる）。

視覚値の正本は repo root の `design.md`。check はその fenced ` ```css ` block（`## Tokens` / `## Components`）を読む。`.css` ファイルを直接渡すこともできる。

## design-md-check.py

```bash
python3 design-md-check.py <design.md> [scan paths...] [--json]
```

`scan paths` を省略すると `design.md` のみを検査する。file または directory（`.css` `.html` `.tsx` `.jsx` `.vue` `.svelte` を再帰的に走査）を渡せる。

| rule | severity | 検出内容 |
| --- | --- | --- |
| `undefined-var` | error | `var(--name)` の参照先が design.md・scan 対象のどこにも定義されていない |
| `fallback-var` | warning | 未定義の `var(--name, fallback)` — fallback がそのまま描画され token 欠落に気づきにくい |
| `contrast-ratio` | warning | WCAG AA 4.5:1 未満の前景/背景。同一 rule block 内の `color`/`background` の組と、`-foreground` 命名規約のペア（`--<name>` / `--<name>-foreground`、`--background` / `--foreground`）の両方を判定する。旧 `on-` 規約のペアも拾う。ペアは scope 単位で判定する（下記「定義の探索範囲と cascade」） |
| `unresolved-color` | info | `oklch()` / `hsl()` / gradient など解決できない色値。コントラスト判定は行わない |
| `no-css-block` | error | `.md` 入力なのに ` ```css ` block が1つも無い |
| `token-summary` | info | 定義された custom property 数と参照数のサマリ |

出力は既定で人間向け1行（`severity rule file:line text — hint`）。`--json` で finding 1件1行の JSONL（`rule`/`severity`/`file`/`line`/`text`/`hint`）を出す。exit code は error が1件以上あれば 1、それ以外は 0。

## 定義の探索範囲と cascade

design.md と scan 対象すべてのファイルに含まれる `--name:` 定義を 1 つの namespace として扱い、同名は後勝ち。CSS の cascade・セレクタ優先順位・テーマ分岐（例: `@media (prefers-color-scheme: dark)` 内の再定義）は一切考慮しない。

例外として `-foreground` ペアの contrast 判定だけは rule block（`:root` / `.dark` 等）をスコープ単位として行う:

- **部分 override は継承解決する**: `.dark` が `--primary` だけを上書きした場合、`--primary-foreground` は外側スコープ（`:root`・トップレベル・scan file）の値を継承してペアを判定する
- **兄弟 scope は継承しない**: `.dark` の定義は `:root` や `.sepia` の判定に混ざらない。外側スコープは `:root` / `html` / `*` のみ（`:root.dark` のような compound は scope 扱い）
- **spec 外のペアも残存パスで判定する**: 両辺が spec の rule block に無いペア（scan file のみの定義等）は外側スコープとして1回判定する

これにより dark 上書きが light の値を潰す誤判定と、片側だけ上書きした場合の検査漏れを両方防ぐ。

design.md だけを正本として厳密にチェックしたい場合は scan paths を渡さない（または `design.md` だけを指定）。

## 未対応（unresolved 扱い）な形式

以下は色値として解決できず `unresolved-color` (severity: info) として報告される:
- CSS nesting（`&` セレクタ）
- custom property の値に `;` `{` `}` を含む data URL や文字列
- `hsl()` / `oklch()` など HSL・LCh 色空間
- gradient（linear-gradient, radial-gradient, conic-gradient）
- alpha < 1.0 の色（背後の色との合成が必要なため判定できない）

半透明の色（rgba や hex 8 桁 alpha）はコントラスト判定の対象外。

## ページ check（page-check）

`design-md-check.py` は design.md 自体（未定義 var 参照・コントラスト比）しか見ておらず、CSS を当てた後の生成ページの構図崩れ（テーブルが使える幅を使わない等）は拾えない。headless Chrome がこの環境で動かないため、レイアウト計測はブラウザ内 JS に分離し、Python は静的ルールと計測 JSON の判定だけを担当する。

```bash
python3 page-check.py <design.md> <page.html> [--layout <measurements.json>] [--allow-classes <file>] [--json]
```

使い方の流れ:

1. 対象ページをブラウザで開く
2. `page-check.js` をコンソール / browser pane の `javascript_tool` / `agent-browser eval --stdin` で実行する（いずれも同じ JS をそのまま使う）
3. 返ってきた JSON（`JSON.stringify` 済みの文字列）をファイルへ保存する
4. `page-check.py <design.md> <page.html> --layout <json>` で判定する

`--allow-classes` にはレイアウト専用など design.md に定義がなくても許容するクラス名を1行1個で列挙する。`--layout` を省略すると静的ルールのみ実行し `layout-skipped` を返す。

| rule | severity | 検出内容 |
| --- | --- | --- |
| `invented-color` | warning | page の `<style>` / `style=` に直書きされた色リテラル（hex/rgb()/hsl()）。design.md の custom property を使うべき箇所 |
| `invented-font` | warning | page の `<style>` / `style=` に直書きされた `font-family` / `font-size`。design.md 由来でないフォント指定 |
| `unknown-class` | info | design.md の css block に `.name` 定義がなく `--allow-classes` にもない class。語彙の欠落・命名揺れの兆候 |
| `negative-without-minus` | warning | `class` に `negative` を含む要素なのにテキストが `-` `−` `▲` のいずれも含まない |
| `no-css-block` | error | `.md` spec 入力なのに ` ```css ` block が1つも無い（全 class が `unknown-class` になるので先に弾く） |
| `external-resource` | error | `<link href="http...">` / `<script src="http...">` / `@import url(http...)` / Google Fonts 参照。固定シナリオのページは外部リソース参照ゼロが前提 |
| `width-usage` | warning | `--layout` 指定時、`table` / `.stat-strip` が親要素の幅を十分（ratio 0.6 未満）使えていない |
| `strip-items-cramped` | warning | `--layout` 指定時、`.stat-strip` の子要素の幅合計が strip 幅に対して小さい（左詰まり） |
| `layout-skipped` | info | `--layout` 未指定。レイアウト判定は skip された |

出力形式・`--json` の JSONL・exit code（error が1件以上あれば 1）の規約は `design-md-check.py` と同じ。

headless Chrome をこの skill に同梱しない理由は、環境依存で起動しないケースがあり、計測はどのブラウザでも同じ JS で済むため。

## アプリの lint 設定の生成（lint-setup）

`design-md-check.py` は design.md 自体を見る。アプリのコードが design.md の token を守っているかは、design.md から生成した lint 設定をアプリに入れて、その repo の stylelint / ESLint に毎回止めさせる。agent が居ない編集でも editor と CI で効く。

```bash
python3 lint-setup.py <design.md> [--out DIR] [--token-file PATH ...] [--tailwind --tailwind-entry PATH] [--check] [--dry-run] [--json]
```

| 生成物 | 条件 | 中身 |
| --- | --- | --- |
| `stylelint.design-md.mjs` | 常に | 色の直書き（hex・named・`rgb()`/`oklch()` 等）を禁止し、色・font・size・line-height・letter-spacing・余白・radius・shadow・easing・duration の property は design.md の token の `var()` と最小限の keyword だけを許す。未定義の token 名も弾く |
| `design-md.theme.css` | `--tailwind` | Tailwind v4 の `@theme inline reference`。token のある namespace（color・font・text・leading・tracking・spacing・radius・shadow・ease）を `initial` で消し、design.md の token だけを utility にする（`bg-red-500`・`p-4` が存在しなくなる） |
| `eslint.design-md.mjs` | 常に | JSX の `style={{ ... }}` で色（hex・`rgb()` 等）の直書きと、色・余白・文字・radius 等の property に `var(--token)` 以外の値を書くことを built-in の `no-restricted-syntax` で禁止する。`--tailwind` 時は `eslint-plugin-better-tailwindcss` の `no-unknown-classes`（上の theme に無い class）と `no-restricted-classes`（`bg-[#fff]`・`p-[13px]` 等の色・余白・文字・radius の任意値）も error にする |

- token の分類は名前（`font-size`・`space`・`radius` 等の語）を優先し、決まらなければ値（色・長さ・時間）で判定する。`--font-weight-*` のように分類できない token は lint の対象外
- `--token-file` に token を定義する CSS（`globals.css` の `:root` 等の Exports）を渡すと、そのファイルだけ stylelint の直書き禁止を外す。path は `--out` からの相対
- 生成物の 1 行目に marker を書く。marker の無い同名ファイルは上書きせず `skipped-not-generated` で exit 1
- `--check` は書き込まずに生成物が design.md と一致するかだけを見る（ずれていれば `stale` で exit 1）。design.md の `## Tokens` を変えたら再生成する
- 出力は 1 ファイル 1 行（`<action> <file>`）と token 数のサマリ。`--json` で JSONL

アプリ側への入れ方（パッケージはその repo の pin・cooldown 規約で入れる）:

- stylelint: `stylelint` を入れ、`stylelint.config.mjs` に `extends: ["./stylelint.design-md.mjs"]`
- ESLint（JSX を書く app）: `eslint.config.mjs` で `import designMd from "./eslint.design-md.mjs"` を配列に `...designMd` で足す（`.tsx` 等の parser 設定は既存のものを使う）。`no-restricted-syntax` は後の設定が同じ rule を書くと丸ごと置き換わるので、既存でも使っていたら selector を 1 つの設定にまとめる
- Tailwind: entry CSS で `@import "tailwindcss";` の後に `@import "./design-md.theme.css";`。`eslint-plugin-better-tailwindcss` を入れ、上の ESLint と同じく `...designMd` で足す
- CI と editor で既存の lint script が走れば、それで強制される。lint-setup 自体を CI で回す必要はない

確認済みの組み合わせ（2026-11）: stylelint 17.16、Tailwind CSS 4（`@tailwindcss/cli`）、ESLint 9 + eslint-plugin-better-tailwindcss 4.10。

共有の解析基盤（`Finding`・`line_of`・`format_human`・fence 抽出・`spec_text`・`strip_comments`）は `check_common.py` に置く。各 script はこれを import する — 同じロジックを各 script にコピーしない。
