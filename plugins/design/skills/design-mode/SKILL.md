---
name: design-mode
description: "UI の見た目・動き・モバイルの触り心地・3D（three.js・React Three Fiber）を作る、直す、レビューするときの入口。新しい画面やサイト、AI っぽい UI の手直し、アニメーション、スワイプやシート、スマホ対応、3D シーン、UI のレビューで使う。場面に合う playbook を開き、そこから design 系の skill を読む。"
---

# design-mode

design plugin の入口。design 系の skill（unslop・design-md・emil 系・threejs-* など）は command only で、ここから辿る。各 skill はこのファイルから見て `../<name>/SKILL.md` にある。playbook で名前を太字にした skill は、その path を開いて読む。

## 常に守ること

- 色・文字・余白・角丸の正本は repo root の `design.md`。無ければ **design-md** で作ってから描く。token に無い値を直書きしない
- 見た目はスクリーンショットで確かめてから終える。コードを読んだだけで「直った」と言わない。動きは録画か、複数フレームのスクリーンショットで見る
- 動きは「そもそも動かすべきか」から決める。`prefers-reduced-motion` を必ず扱う
- ライブラリを足す前に **pick-ui-library** を見る

## playbook

場面に合う playbook を `playbooks/<name>.md` から開き、手順を todo に写してから進める。

| 場面 | playbook |
| --- | --- |
| 新しい画面・サイト・視覚システムを作る | `new-surface.md` |
| 既存 UI の手直し、AI っぽさを消す | `polish.md` |
| 動きをつける・直す | `motion.md` |
| 既存の動きを棚卸しする（足す・削る・直す計画） | `motion-audit.md` |
| スマホで触ったときの感じを整える | `mobile-feel.md` |
| 3D シーンを作る・直す | `3d.md` |
| UI の変更をレビューする | `ui-review.md` |

どれにも当たらないときは、近い playbook の手順から必要なものだけ使い、何を省いたかを報告に書く。
