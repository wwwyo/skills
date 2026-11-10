#!/usr/bin/env python3
"""Render a domain model (TS type block + optional viz spec) into one HTML file.

Usage:
  python3 domain_viz.py --types model.ts [--spec viz.json] --out domain.html
  python3 domain_viz.py --types model.ts --dump   # print parsed data as JSON

Input formats are defined in ../references/domain-viz.md. Standard library only.
"""
import argparse
import json
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "domain-viz.html"
PLACEHOLDER = "/*__DATA__*/null"
INLINE_ENUM_MAX = 12  # literal unions up to this size are shown inline, larger ones open as a box

AGG_HEAD = re.compile(r"^//\s*=====\s*(.+?)\s*$")
SHARED_HEAD = re.compile(r"^//\s*-----")
RULE = re.compile(r"^//\s*(?:守ること|invariant)\s*[:：]\s*(.+)$", re.I)
TYPE_DECL = re.compile(r"^(?:export\s+)?type\s+([^\s<=]+)(?:<.*?>)?\s*=\s*(.*)$")
FIELD = re.compile(r"^\s+(?:readonly\s+)?([^?:\s]+)(\?)?\s*:\s*(.*?)\s*;?\s*(?://\s*(.*))?$")
KEY = re.compile(r"^(PK|FK)(?:\s*[・/,、]\s*(PK|FK))?(?:\s*[。:：]\s*|\s+|$)")
LITERAL = re.compile(r"'[^']*'|\"[^\"]*\"")

ID_NAME = re.compile(r"(ID|Id|コード|Code|Key)$")
DATE_NAME = re.compile(r"年度|日付|日時|時刻|Date|Time|At$")
URL_NAME = re.compile(r"^(URL|Url|url)$|URL$")
MASTER_NOTE = re.compile(r"マスタ|master", re.I)


class ParseError(Exception):
    pass


def split_comment(text):
    """Split `code // comment` while ignoring // inside string literals."""
    in_str = None
    for i, ch in enumerate(text):
        if in_str:
            if ch == in_str:
                in_str = None
        elif ch in "'\"":
            in_str = ch
        elif text.startswith("//", i):
            return text[:i].rstrip(), text[i + 2:].strip()
    return text.rstrip(), ""


def parse_field(line, lineno):
    code, comment = split_comment(line)
    m = FIELD.match(code)
    if not m:
        raise ParseError(f"line {lineno}: cannot read field: {line.strip()}")
    name, opt, ty = m.group(1), bool(m.group(2)), m.group(3).strip().rstrip(";").strip()
    key = ""
    k = KEY.match(comment)
    if k:
        key = "・".join(x for x in (k.group(1), k.group(2)) if x)
        comment = comment[k.end():].strip()
    return {"name": name, "optional": opt, "type": ty, "note": comment, "key": key}


def parse_types(text):
    types = {}
    aggs = []
    cur = None
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        lineno = i + 1
        if m := AGG_HEAD.match(line):
            cur = {"title": m.group(1), "rules": [], "types": []}
            aggs.append(cur)
        elif SHARED_HEAD.match(line):
            cur = None
        elif m := RULE.match(line):
            if cur is None:
                raise ParseError(f"line {lineno}: invariant outside an aggregate")
            cur["rules"].append(m.group(1).strip())
        elif m := TYPE_DECL.match(line):
            name = m.group(1)
            rhs, note = split_comment(m.group(2))
            rhs = rhs.strip().rstrip(";").strip()
            if rhs.endswith("{"):
                base = rhs[:-1].strip().rstrip("&").strip() or None
                rows = []
                i += 1
                while i < len(lines) and not lines[i].startswith("}"):
                    body = lines[i]
                    if body.strip() and not body.strip().startswith("//"):
                        rows.append(parse_field(body, i + 1))
                    i += 1
                if i >= len(lines):
                    raise ParseError(f"line {lineno}: unterminated object type {name}")
                types[name] = {"kind": "obj", "rows": rows, "note": note, "base": base}
            else:
                if rhs == "":  # multi-line union: type X =\n  | A\n  | B
                    parts = []
                    while i + 1 < len(lines) and lines[i + 1].strip().startswith("|"):
                        i += 1
                        code, c = split_comment(lines[i].strip()[1:])
                        parts.append(code.strip().rstrip(";"))
                        note = note or c
                    rhs = " | ".join(parts)
                types[name] = {"kind": "alias", "rhs": rhs, "note": note}
            if cur is not None:
                cur["types"].append(name)
        i += 1
    for a in aggs:
        if not a["types"]:
            raise ParseError(f"aggregate '{a['title']}' has no type")
    return types, aggs


class Model:
    def __init__(self, types, aggs):
        self.types = types
        self.aggs = aggs
        self.bases = {t["base"] for t in types.values() if t.get("base")}
        for b in self.bases:
            if b not in types or types[b]["kind"] != "obj":
                raise ParseError(f"base type '{b}' must be an object type")

    def literals(self, name):
        t = self.types.get(name)
        if not t or t["kind"] != "alias":
            return None
        parts = [p.strip() for p in t["rhs"].split("|")]
        if parts and all(LITERAL.fullmatch(p) for p in parts):
            return parts
        return None

    def is_enum(self, name):
        return self.literals(name) is not None

    def is_union(self, name):
        t = self.types.get(name)
        if not t or t["kind"] != "alias" or self.is_enum(name):
            return False
        parts = [p.strip() for p in t["rhs"].split("|")]
        return len(parts) > 1 and all(p in self.types for p in parts)

    def boxable(self, name):
        t = self.types.get(name)
        return bool(t) and name not in self.bases and (
            t["kind"] == "obj" or self.is_union(name)
            or (self.is_enum(name) and len(self.literals(name)) > INLINE_ENUM_MAX))

    def rows(self, name):
        t = self.types[name]
        return (self.rows(t["base"]) if t.get("base") else []) + t["rows"]

    def kind_of(self, expr):
        e = re.sub(r"<.*>", "", expr).strip()
        if e.endswith("[]"):
            return "arr"
        if e == "boolean":
            return "bool"
        if LITERAL.search(e):
            return "enum"
        if " & " in e or e.startswith("{"):
            return "obj"
        if " | " in e:
            parts = [p.strip() for p in e.split("|")]
            if all(p in self.types for p in parts):
                return "obj"
        return self.kind_of_name(e)

    def kind_of_name(self, name, seen=()):
        if name in ("string",):
            return "text"
        if name in ("number", "bigint"):
            return "num"
        if name == "boolean":
            return "bool"
        t = self.types.get(name)
        if not t:
            return "text"
        if t["kind"] == "obj" or self.is_union(name):
            return "obj"
        if self.is_enum(name) or MASTER_NOTE.search(t["note"]):
            return "enum"
        if ID_NAME.search(name):
            return "id"
        if DATE_NAME.search(name):
            return "date"
        if URL_NAME.search(name):
            return "url"
        rhs = t["rhs"]
        if rhs in self.types and rhs not in seen:
            return self.kind_of_name(rhs, seen + (name,))
        return self.kind_of(rhs) if rhs != name else "text"

    def box(self, name):
        t = self.types[name]
        if t["kind"] == "obj":
            rows = self.rows(name)
        elif self.is_enum(name):
            rows = [{"name": "", "optional": False, "type": t["rhs"], "note": "", "key": ""}]
        else:
            rows = [{"name": "次のどれか", "optional": False, "type": t["rhs"], "note": "", "key": ""}]
        out = []
        for r in rows:
            out.append([r["name"], r["optional"], r["type"], r["note"], r["key"], self.kind_of(r["type"])])
        kind = "enum" if self.is_enum(name) else "obj"
        return {"name": name, "note": t["note"], "kind": kind, "rows": out}

    def refs(self, box):
        found = []
        for r in box["rows"]:
            expr = LITERAL.sub("", r[2])
            for tok in re.findall(r"[^\s<>\[\]{}|&,:;()=]+", expr):
                if tok != box["name"] and self.boxable(tok) and tok not in found:
                    found.append(tok)
        return found

    def inline_enums(self):
        return {n: self.literals(n) for n in self.types
                if self.is_enum(n) and len(self.literals(n)) <= INLINE_ENUM_MAX}

    def aggregates(self):
        out = []
        for a in self.aggs:
            root = a["types"][0]
            if self.types[root]["kind"] != "obj":
                raise ParseError(f"root type '{root}' of '{a['title']}' must be an object type")
            order, todo = [], [root]
            while todo:
                n = todo.pop(0)
                if n in order:
                    continue
                order.append(n)
                todo += self.refs(self.box(n))
            title = a["title"]
            name_m = re.match(r"^(.*?)\s*[（(]", title)
            desc_m = re.search(r"[)）]\s*[:：]\s*(.+)$", title)
            out.append({
                "title": title,
                "name": root,
                "label": name_m.group(1) if name_m else root,
                "description": desc_m.group(1) if desc_m else "",
                "proposed": "★" in title,
                "rule": "。".join(r.rstrip("。") for r in a["rules"]),
                "boxes": [self.box(n) for n in order],
            })
        return out

    def auto_refs(self, aggs):
        """Edges from FK fields whose type is another root's single-PK type."""
        pk_owner = {}
        for a in aggs:
            pks = [r for r in a["boxes"][0]["rows"] if "PK" in r[4]]
            if len(pks) == 1 and "FK" not in pks[0][4]:
                pk_owner[pks[0][2]] = a["name"]
        edges = []
        for a in aggs:
            for b in a["boxes"]:
                for r in b["rows"]:
                    target = pk_owner.get(r[2])
                    if not target or "FK" not in r[4]:
                        continue
                    label = "" if r[0] == target else r[0]
                    e = {"from": a["name"], "to": target, "label": label}
                    if e not in edges:
                        edges.append(e)
        return edges


def build_overview(model, aggs, spec):
    ov = dict(spec.get("overview") or {})
    by_name = {a["name"]: a for a in ov.get("aggregates", [])}
    unknown = set(by_name) - {a["name"] for a in aggs}
    if unknown:
        raise ParseError(f"overview.aggregates not found in types: {sorted(unknown)}")
    merged = []
    for a in aggs:
        s = by_name.get(a["name"], {})
        merged.append({
            "name": a["name"],
            "label": s.get("label", ""),
            "responsibility": s.get("responsibility", a["description"]),
            "invariant": s.get("invariant", a["rule"]),
            "proposed": s.get("proposed", a["proposed"]),
            "children": s.get("children", []),
        })
    ov["aggregates"] = merged
    if "refs" not in ov:
        ov["refs"] = model.auto_refs(aggs)
    names = {a["name"] for a in merged} | {c["name"] for a in merged for c in a["children"]}
    for e in ov["refs"]:
        for end in (e["from"], e["to"]):
            if end not in names:
                raise ParseError(f"overview.refs endpoint '{end}' is not an aggregate or child node")
    return ov


def check_db(db):
    tables = {}
    for d in db.get("domains", []):
        for t in d.get("tables", []):
            if t["name"] in tables:
                raise ParseError(f"db table '{t['name']}' defined twice")
            tables[t["name"]] = t
    for d in db.get("domains", []):
        for t in d.get("tables", []):
            for c in t.get("columns", []):
                if c.get("ref") and c["ref"] not in tables:
                    raise ParseError(f"db column {t['name']}.{c['name']} refs unknown table '{c['ref']}'")
        for r in d.get("relations", []):
            for end in (r["from"], r["to"]):
                if end not in tables:
                    raise ParseError(f"db relation endpoint '{end}' is not a defined table")


def build(types_text, spec):
    types, raw_aggs = parse_types(types_text)
    model = Model(types, raw_aggs)
    aggs = model.aggregates()
    data = {
        "title": spec.get("title", "ドメインモデル"),
        "lead": spec.get("lead", ""),
        "overview": build_overview(model, aggs, spec),
        "aggregates": aggs,
        "inlineEnums": model.inline_enums(),
        "db": spec.get("db"),
    }
    if data["db"]:
        check_db(data["db"])
    return data


def render(data, template_text):
    if PLACEHOLDER not in template_text:
        raise ParseError(f"template has no {PLACEHOLDER} placeholder")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = data["title"].replace("&", "&amp;").replace("<", "&lt;")
    return template_text.replace(PLACEHOLDER, payload).replace("__TITLE__", title)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--types", required=True, help="TS type block (one file)")
    p.add_argument("--spec", help="viz spec JSON (overview / db); optional")
    p.add_argument("--out", help="output HTML path")
    p.add_argument("--template", default=str(TEMPLATE), help="HTML template")
    p.add_argument("--dump", action="store_true", help="print parsed data JSON instead of HTML")
    a = p.parse_args(argv)
    try:
        spec = json.loads(Path(a.spec).read_text()) if a.spec else {}
        data = build(Path(a.types).read_text(), spec)
        if a.dump:
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0
        if not a.out:
            p.error("--out is required unless --dump")
        Path(a.out).write_text(render(data, Path(a.template).read_text()))
    except (ParseError, json.JSONDecodeError, KeyError, OSError) as e:
        print(f"domain_viz: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    summary = {"out": a.out, "aggregates": [x["name"] for x in data["aggregates"]],
               "tables": sum(len(d.get("tables", [])) for d in (data["db"] or {}).get("domains", []))}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
