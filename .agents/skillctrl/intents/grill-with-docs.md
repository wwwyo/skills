# grill-with-docs

## 文脈

pi・Claude Code で同じ skill を使い、文書作成からも呼び出す。特定 harness の Skill tool 名だけでは実行できない。

## 意図

grilling と domain-modeling の本文を読んで併用する入口にする。質問と記録の規約を重複させず、合意していない判断は記録しない。

- 自動で読まれる skill を減らすため（2026-11-28、ユーザー判断）、`disable-model-invocation: true` を付けて command only にする。mode の Feature playbook と prd・document からリンクで辿られる
