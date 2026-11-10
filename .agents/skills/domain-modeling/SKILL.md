---
name: domain-modeling
description: Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing the Glossary section of AGENTS.md, recording or editing an ADR, or writing the model as strict TS types and visualizing aggregates, types, and tables as one HTML page.
---

# Domain Modeling

Actively build and sharpen the project's domain model as you design. This is the *active* discipline: challenging terms, inventing edge-case scenarios, and writing the glossary and decisions down the moment they crystallise. (Merely *reading* the Glossary for vocabulary is not this skill: that's a one-line habit any skill can do. This skill is for when you're changing the model, not just consuming it.)

## File structure

```
/
├── AGENTS.md          ← `## Glossary` section is the glossary
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

The glossary lives in `AGENTS.md` because it is the one file every session reads unconditionally; a separate glossary file would only be read when someone remembers to. Create things lazily: add the `## Glossary` section when the first term is resolved, create `docs/adr/` when the first ADR is needed. If `AGENTS.md` itself does not exist, create it at the repo root.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in the Glossary, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y. Which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account': do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible. Which is right?"

### Update the Glossary inline

When a term is resolved, update the `## Glossary` section of `AGENTS.md` right there. Don't batch these up: capture them as they happen. Use the term format in [references/glossary-format.md](references/glossary-format.md).

The Glossary should be totally devoid of implementation details. Do not treat it as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else. Other sections of `AGENTS.md` are not touched by this skill.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse**: the cost of changing your mind later is meaningful
2. **Surprising without context**: a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off**: there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. Use the format in [document ADR format](../document/references/adr-format.md).

## Visualize the model

When aggregates, their types, or the table design are being decided (or reviewed with someone), write the model as TS types and render it as one HTML page: 1. aggregate overview, 2. types per aggregate, 3. table design.

- Keep the types in one TS block next to the decision docs (e.g. `docs/domain-model.ts`). Mark aggregates with `// ===== Title` (first type = root), shared types with `// -----`, invariants with `// 守ること:`, and key columns with a leading `PK` / `FK` / `PK・FK` in the field comment.
- Make the types precise: one alias per ID or value, unions of object types wherever the shape changes, literal unions for fixed values. Check with `tsc --strict --noEmit --lib es2022`.
- Put what types cannot say (responsibilities, inner nodes of the overview, DB tables, proposals) in a JSON spec, then run `python3 tools/domain_viz.py --types <ts> --spec <json> --out <html>` from this skill's directory and open the result.

Formats and conventions: [references/domain-viz.md](references/domain-viz.md).
