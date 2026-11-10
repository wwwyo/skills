# Domain model visualization

One HTML page in three parts, generated from two inputs:

| Part | Shows | Input |
| --- | --- | --- |
| 1. 集約の概要 | roots, what each aggregate owns, ID references between aggregates | type block (+ `overview` in spec) |
| 2. model の詳細 | each aggregate's types as boxes: PK/FK, optional, union, enum; click a type to expand it in place | type block |
| 3. table 設計 | DB tables per area as ER boxes: PK/FK/判断 columns, proposed tables | `db` in spec |

```sh
python3 tools/domain_viz.py --types model.ts [--spec viz.json] --out domain.html
python3 tools/domain_viz.py --types model.ts --dump   # parsed data, for debugging
```

Python 3 standard library only. The page loads mermaid (pinned, SRI) from jsDelivr for the diagrams. Example inputs: [assets/domain-viz-example/](../assets/domain-viz-example/).

## Type block (`--types`)

A plain TS file of `type` declarations. It must pass `tsc --strict --noEmit --lib es2022 model.ts` (`--lib es2022` keeps DOM globals such as `URL` from colliding).

- `// ===== <Title>` starts an aggregate. The first `type` after it is the root and must be an object type. Title convention: `Name（root）: what one instance is`; the text after `:` becomes the default responsibility, and `★` in the title marks a proposal.
- `// ----- <label>` starts shared types (value types, IDs, masters) that belong to no aggregate.
- `// 守ること: …` (or `// invariant: …`) inside an aggregate is its invariant.
- Field comments: `name?: Type  // PK・FK。note`. A leading `PK`, `FK` or `PK・FK` (followed by `。`, space or end) becomes the key badge; the rest is the note.
- Give every ID and value its own alias (`type 注文ID = string`), and model shape changes as unions of object types (`type 支払い = カード払い | 振込`, each with a literal discriminator) instead of optional fields that only apply sometimes.
- `type A = Base & { … }` merges Base's fields into A; Base is not drawn on its own.
- Icon kinds come from the alias chain: literal union → choice; alias whose comment says `マスタ`/`master` → choice; name ending in `ID`/`コード`/`Code`/`Key` → ID; name containing `年度`/`日付`/`Date`/… → date; `URL` → link; otherwise the primitive.
- Literal unions with up to 12 values show inline; larger ones open as a box.

Part 2 draws every object/union type reachable from the root, so shared types appear in each aggregate that uses them.

## Spec (`--spec`, JSON, optional)

```jsonc
{
  "title": "…", "lead": "…",
  "overview": {
    "intro": "…",
    "aggregates": [            // by root type name; omitted fields fall back to the type block
      {"name": "注文", "label": "1回の購入", "responsibility": "…", "invariant": "…", "proposed": false,
       "children": [{"name": "明細"}, {"name": "支払い", "parent": "注文", "label": "…"}]}  // parent defaults to the previous child
    ],
    "refs": [{"from": "明細", "to": "商品", "label": "…"}],   // omit to derive from FK fields typed as another root's single PK
    "notes": ["…"]
  },
  "db": {
    "intro": "…",
    "domains": [
      {"name": "注文（order）", "proposed": false, "intro": "…",
       "tables": [{"name": "orders", "root": true, "columns": [
         {"name": "order_id", "type": "string", "key": "PK"},
         {"name": "customer_id", "type": "string", "key": "FK", "ref": "customer",
          "optional": false, "judgment": false, "note": "…", "card": "}o--||", "label": "…"}
       ]}],
       "relations": [{"from": "a", "card": "||--|{", "to": "b", "label": ""}]}
    ]
  }
}
```

- `ref` draws a relation: `}o--||`, or `}o--o|` when `optional`; `card` / `label` override. Label defaults to the column name.
- `judgment: true` marks a reference the product decided (matching, classification) rather than a fact from the source; it is tagged `判断` on the column and the line.
- A table referenced from another area is drawn there with its PK columns only.
- `root: true` colours the table green. `proposed: true` on a domain titles it `★ …（案）` and excludes it from the table count.
- `relations` is for lines a column cannot express (1:1, parent-child without FK column, derived links).
