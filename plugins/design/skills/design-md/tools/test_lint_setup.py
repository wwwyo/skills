"""lint-setup.py の unittest。生成した設定が oxlint で動くかは README の手順で確かめる。"""

import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_spec = importlib.util.spec_from_file_location("lint_setup", Path(__file__).parent / "lint-setup.py")
lint = importlib.util.module_from_spec(_spec)
sys.modules["lint_setup"] = lint
_spec.loader.exec_module(lint)

DESIGN = """# Design — test

## Tokens

```css
:root {
  --background: #ffffff;
  --foreground: #111111;
  --primary: oklch(50% 0.1 160);
  --primary-foreground: #ffffff;
  --ring: var(--primary);
  --radius: 6px;
  --radius-card: calc(var(--radius) * 2);
  --font-family-jp: "Noto Sans JP", sans-serif;
  --font-weight-bold: 700;
  --font-size-body: 15px;
  --line-height-body: 1.8;
  --letter-spacing-body: 0.04em;
  --space-sm: 8px;
  --shadow-sm: 0 2px 6px rgba(0, 0, 0, 0.08);
  --duration-fast: 120ms;
}
.dark { --background: #000000; }
```
"""


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = lint.main(argv)
    return code, out.getvalue(), err.getvalue()


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "design.md"
            p.write_text(DESIGN, encoding="utf-8")
            self.groups = lint.group_tokens(lint.parse_tokens(p))

    def test_categories(self):
        g = self.groups
        self.assertEqual(g["color"], ["--background", "--foreground", "--primary", "--primary-foreground", "--ring"])
        self.assertEqual(g["radius"], ["--radius", "--radius-card"])
        self.assertEqual(g["font-family"], ["--font-family-jp"])
        self.assertEqual(g["font-size"], ["--font-size-body"])
        self.assertEqual(g["line-height"], ["--line-height-body"])
        self.assertEqual(g["letter-spacing"], ["--letter-spacing-body"])
        self.assertEqual(g["space"], ["--space-sm"])
        self.assertEqual(g["shadow"], ["--shadow-sm"])
        self.assertEqual(g["duration"], ["--duration-fast"])

    def test_text_alias_follows_referenced_token(self):
        tokens = {"--muted": "#888888", "--text-muted": "var(--muted)", "--text-body": "15px"}
        self.assertEqual(lint.classify("--text-muted", "var(--muted)", tokens), "color")
        self.assertEqual(lint.classify("--text-body", "15px", tokens), "font-size")

    def test_font_weight_is_not_a_family(self):
        self.assertNotIn("--font-weight-bold", sum(self.groups.values(), []))

    def test_dark_override_is_not_duplicated(self):
        self.assertEqual(self.groups["color"].count("--background"), 1)


class GenerateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.design = self.dir / "design.md"
        self.design.write_text(DESIGN, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def config(self):
        text = (self.dir / lint.CONFIG_FILE).read_text(encoding="utf-8")
        self.assertIn(lint.MARKER, text.splitlines()[0])
        return json.loads(text.split("\n", 1)[1])

    def test_no_tailwind_by_default(self):
        code, _, _ = run([str(self.design)])
        self.assertEqual(code, 0)
        self.assertFalse((self.dir / lint.THEME_FILE).exists())
        cfg = self.config()
        self.assertEqual(cfg["jsPlugins"], ["./" + lint.PLUGIN_FILE])
        self.assertEqual(cfg["rules"], {"design-md/no-raw-style": "error"})
        plugin = (self.dir / lint.PLUGIN_FILE).read_text(encoding="utf-8")
        self.assertIn('"paddingTop": "space"', plugin)
        self.assertIn('"primary-foreground"', plugin)

    def test_components_are_exempt(self):
        run([str(self.design), "--tailwind", "--tailwind-entry", "app.css"])
        override = self.config()["overrides"][0]
        self.assertEqual(override["files"], ["**/components/**"])
        self.assertEqual(override["rules"]["design-md/no-raw-style"], "off")
        self.assertEqual(override["rules"]["better-tailwindcss/no-restricted-classes"], "off")
        # typo の検出は component でも残す
        self.assertNotIn("better-tailwindcss/no-unknown-classes", override["rules"])

    def test_custom_component_glob(self):
        run([str(self.design), "--component-glob", "src/ui/**"])
        self.assertEqual(self.config()["overrides"][0]["files"], ["src/ui/**"])

    def test_tailwind_theme_maps_tokens_without_reset(self):
        run([str(self.design), "--tailwind", "--tailwind-entry", "src/app.css"])
        css = (self.dir / lint.THEME_FILE).read_text(encoding="utf-8")
        self.assertIn("@theme inline reference {", css)
        self.assertNotIn("initial", css.split("{", 1)[1])
        self.assertIn("--color-primary: var(--primary);", css)
        self.assertIn("--font-jp: var(--font-family-jp);", css)
        self.assertIn("--text-body: var(--font-size-body);", css)
        self.assertIn("--spacing-sm: var(--space-sm);", css)
        self.assertIn("--radius: var(--radius);", css)
        rules = self.config()["rules"]
        self.assertEqual(rules["better-tailwindcss/no-unknown-classes"], ["error", {"entryPoint": "src/app.css"}])

    def test_restricted_class_patterns(self):
        groups = lint.group_tokens(lint.parse_tokens(self.design))
        pats = [re.compile(r["pattern"]) for r in lint.restricted_class_patterns(groups)]
        hit = lambda c: any(p.match(c) for p in pats)
        for cls in ("bg-[#fff]", "md:p-[13px]", "data-[state=open]:bg-[#fff]", "[&>svg]:p-4", "[color:#fff]", "hover:[padding:13px]", "hover:text-[var(--x)]", "-mt-[2px]", "bg-red-500", "text-white/50",
                    "p-4", "gap-x-2", "text-sm", "rounded-lg", "rounded-t-md", "shadow-md", "font-sans", "leading-6", "tracking-wide"):
            self.assertTrue(hit(cls), cls)
        for cls in ("bg-primary", "p-sm", "text-body", "text-center", "shadow-sm", "rounded-full", "rounded-card",
                    "font-jp", "font-bold", "grid-cols-[1fr_2fr]", "w-[320px]", "bg-transparent", "flex", "data-[state=open]:bg-primary", "[mask-type:luminance]"):
            self.assertFalse(hit(cls), cls)

    def test_tailwind_requires_entry(self):
        code, _, err = run([str(self.design), "--tailwind"])
        self.assertEqual(code, 2)
        self.assertIn("--tailwind-entry", err)

    def test_tailwind_name_collision_is_error(self):
        self.design.write_text(DESIGN.replace("--ring: var(--primary);", "--color-primary: #000000;"), encoding="utf-8")
        code, _, err = run([str(self.design), "--tailwind", "--tailwind-entry", "app.css"])
        self.assertEqual(code, 2)
        self.assertIn("--color-primary", err)

    def test_empty_category_is_still_checked(self):
        self.design.write_text("# Design\n\n```css\n:root { --primary: #123456; }\n```\n", encoding="utf-8")
        run([str(self.design)])
        plugin = (self.dir / lint.PLUGIN_FILE).read_text(encoding="utf-8")
        self.assertIn('"padding": "space"', plugin)

    def test_check_detects_drift(self):
        run([str(self.design)])
        self.assertEqual(run([str(self.design), "--check"])[0], 0)
        self.design.write_text(DESIGN.replace("--space-sm: 8px;", "--space-sm: 8px;\n  --space-md: 16px;"), encoding="utf-8")
        code, out, _ = run([str(self.design), "--check"])
        self.assertEqual(code, 1)
        self.assertIn("stale", out)

    def test_dry_run_writes_nothing(self):
        code, out, _ = run([str(self.design), "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("would-write", out)
        self.assertFalse((self.dir / lint.CONFIG_FILE).exists())

    def test_does_not_overwrite_hand_written_file(self):
        target = self.dir / lint.CONFIG_FILE
        target.write_text("{}\n", encoding="utf-8")
        code, out, _ = run([str(self.design)])
        self.assertEqual(code, 1)
        self.assertIn("skipped-not-generated", out)
        self.assertEqual(target.read_text(encoding="utf-8"), "{}\n")

    def test_rejects_paths_outside_out(self):
        code, _, err = run([str(self.design), "--component-glob", "../x/**"])
        self.assertEqual(code, 2)
        self.assertIn("相対 path", err)

    def test_no_tokens_is_error(self):
        self.design.write_text("# Design\n\n```css\n.a { color: red; }\n```\n", encoding="utf-8")
        self.assertEqual(run([str(self.design)])[0], 2)


if __name__ == "__main__":
    unittest.main()
