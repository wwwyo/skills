## メモリ（wiki）

この home の memory は [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 型で持つ。原本は `raw/`（LLM は書き換えない）、LLM が書いて維持する合成知識が `wiki/`、その schema が [wiki/AGENTS.md](./wiki/AGENTS.md)。session は終われば文脈を失うので、次の session が聞き直さずに済む理解・判断・PJ の位置づけを wiki に残し、必要なときに必要な節だけ引く。

- 引くのは、過去の判断や PJ の文脈が要るとき、対象 repo の code・AGENTS.md・ADR だけでは背景が足りないときだけ。通常の実装では事前に読まない
- 書くのは、repo をまたいで転用できる理解・判断が生まれたときだけ。repo の決定は対象 repo の ADR、手順は skill、repo の制約は AGENTS.md に置き、wiki に写さない
- 引き方・書き方・検査（`python3 tools/okf_check.py wiki`）は [wiki/AGENTS.md](./wiki/AGENTS.md) に従う
