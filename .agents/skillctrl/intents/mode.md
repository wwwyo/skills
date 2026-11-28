# mode の適応意図

pstack の poteto-mode を `mode` の名前で取り込み、コード作業の入口にする（2026-11-27、ユーザー判断）。旧 implement・pr・ce-simplify-code・prototype skill はこの skill の playbook と upstream の opening-a-pr・babysit に置き換えた。原本の Non-negotiables・Principles・playbook の骨格は保つ。

- 自動起動する。入口なので `disable-model-invocation` は付けない（自動起動は mode と typescript-best-practices だけ）
- Cursor 固有の前提を外す。`poteto-agent`・`/setup-pstack`・model の slug 表・Fable/Gemini の扱い・`cursor-team-kit` の deslop/control-ui を参照しない。subagent は親と同じ model で、`model` を渡さない。core から local の delegate を参照しない
- pstack で取り込まなかった skill（arena・swarm・show-me-your-work・why・how・bro・principle-guard-the-context-window など）を参照しない。arena は代替の手順を足さず、指定を消すだけにする。N 体並べる手順は入れない
- 文章は unslop-writing、UI の確認は e2e skill、stack の構築は gh-stack を使う
- playbook から authoring-a-skill・worktree-cleanup（と worktree-audit.sh）・session-pickup を外す。環境ごとの手順はこの repo の他 skill が持つ
- feature playbook は機能設計も担う。不明確な依頼は grill-with-docs、要件は prd、形が不明なら Prototype playbook で詰めてから architect へ進む。設計だけ頼まれたら architect で止める。PRD を実装するときは status を更新する。テストは E2E・API・unit の順で選ぶ
- prototype playbook は UI の試作が主。動きを比べるときだけ emil-design-eng の基準に揃え、コード品質は問わない
- review-triage は bot と人間の両方のレビューコメントを同じ基準で裁く（原本の bugbot-triage を一般化）
- PR は ready で開き、pr-auto-merge の対象にしてよい
- watch-pr の bootstrap は原本どおり frozen な bun.lock を使う。dev 依存は `latest` ではなく lock が解決した版を exact で書く（repo の exact ピンの規約）。test と型検査は `tests/mode-watch-pr.test.sh` で CI に載せる
- playbook から watcher を指す path は `../scripts/watch-pr/watch-pr` と playbook からの相対で書く
- wwwyo 独自の Review playbook（`playbooks/review.md`）を持つ。PR を head の内容で判定する側の手順で、受けたレビューを捌く review-triage とは逆向き。観点は Principles の leaf と blast-radius に結び付け、wwwyo の must（平文の秘密・`*.local.*` の commit・依存の範囲指定）を持つ。投稿の仕方と approve の条件は呼び出し側（Orca の Auto Approve bot の pr-review など）に残す。Non-negotiables と playbook 一覧、description に Review を足す（2026-11-28、ユーザー判断）
- Review playbook で書くレビューは、Non-negotiables の「返答で原則を名指しする」の例外にする（指摘は結果の重さで書く）
- 自動で読まれる skill を減らすため（2026-11-28、ユーザー判断）、command only にした skill へ playbook から辿る。Feature の step 2 から domain-modeling・database-design・agent-friendly-cli と design-mode へ、Prototype から design-mode へ
