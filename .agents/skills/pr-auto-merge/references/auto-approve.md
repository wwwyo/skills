# Auto Approve への再レビュー依頼

Auto Approve（Orca のレビュー bot）は、オーナー（wwwyo）とオーナーの `gh` で動く agent による push・ready 化を通知されないため、初回レビュー後の修正を見落とす。PR に `@orca-bots` を含むコメントを書くと起動するので、次の 2 つの時点でだけ依頼する。

- ready の PR に push した直後（レビュー対応の修正、pr-auto-merge の dispatch による修復を含む）。1 回の push に commit が複数あってもコメントは 1 つ
- `gh pr ready` で draft を解除した直後。push してから ready にする流れでは、この 1 回だけ書く

PR を作った直後（作成時は bot が自動でレビューする）と、draft のままの push では書かない。

対象 repo（この一覧の正本。他の skill はこの節を参照し、一覧を複製しない）:

- wwwyo/{me, wwwyo, tools, dotfiles, slidex, skills, hyperframes, marketingskills}
- fudoki-hensansitu/{home, fudoki, prototype, auth}

```bash
# <PR URL> の repo が対象のときだけ。push 後は isDraft: false のときだけ
sha=$(gh pr view <PR URL> --json headRefOid --jq '.headRefOid[0:7]')
gh pr comment <PR URL> --body "@orca-bots 再レビュー: ${sha}（修正を push した）"   # ready 化の直後は「ready にした」
```

失敗しても（Orca が無い環境・`gh` が使えないなど）作業は止めず、依頼できなかったことを報告に残す。

依頼したら PR の監視（mode の babysit playbook）に戻り、Auto Approve のレビューを「開始されたレビュー」として終了条件に数える。bot は依頼の直後に `orca-bots` 名義で `Working…` とだけ書いたコメントを付け、レビューが終わると結果（must / should / nit）を新しいコメントとして投稿する。返信なしで終わった run では `Working…` が残るので、`Working…` の有無では判定しない。依頼より後に `Working…` 以外の `orca-bots` のコメントが付いたら終了とみなし、指摘は AI レビューボットのコメントとして babysit の review triage で扱う。依頼から 15 分たっても結果のコメントが無ければ、`Working…` が残っていても未確認としてユーザーに報告して先へ進む。

## 手動 merge の後

ユーザーやエージェントが lane を通さずに merge したときも、merge 後の片付けは `pr_triage.py sweep` に任せる（[tick の手順](../SKILL.md#tick-の手順executor-session)）。dotfiles の変更を merge したら、完了報告の前に canonical checkout（`~/src/github.com/wwwyo/dotfiles`）を pull して `~` 側への反映を確認する（dir link 配下は merge 時点で即届くが、chezmoi apply が要る file もある）。
