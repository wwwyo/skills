# domain-modeling の適応意図

ADR の書式は document skill に置き、元の軽い形式（タイトルと1〜3文、付加セクションは任意）を保つ。
文書作成の入口を document にまとめるため、domain-modeling からは移動先の reference を参照する。
用語を詰める役割と、設計議論の途中で ADR を提案する条件は domain-modeling に残す。

ドメインモデルは tsc --strict を通る厳密な TS の型で書き、1枚の HTML で「集約の概要・model の詳細・table 設計」を可視化できるようにする。
型で決まる形（集約・root・PK/FK・任意・union・enum）は型ブロックを正とし、型で書けない責務・概要図の内部ノード・DB の表・案は別の JSON spec に置く。
生成器は python3 標準ライブラリだけで動き、入力・出力のパスを引数で受ける。特定プロダクトの名前・表・データは template と生成器に持たせない。
SKILL.md には「いつ可視化するか・型の書き方の要点・生成コマンド」だけを置き、入力形式の詳細は reference に置く。
