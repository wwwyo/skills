"""lint-setup.py の unittest。生成した設定が stylelint / ESLint で動くかは README の手順で確かめる。"""

import importlib.util
import io
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

    def test_stylelint_only_by_default(self):
        code, out, _ = run([str(self.design)])
        self.assertEqual(code, 0)
        self.assertTrue((self.dir / lint.STYLELINT_FILE).exists())
        self.assertFalse((self.dir / lint.THEME_FILE).exists())
        js = (self.dir / lint.STYLELINT_FILE).read_text(encoding="utf-8")
        self.assertIn(lint.MARKER, js.splitlines()[0])
        self.assertIn(r"var\(--(?:background|foreground|primary|primary-foreground|ring)\)", js)
        self.assertIn('"padding": [space]', js)

    def test_token_file_override(self):
        run([str(self.design), "--token-file", "src/tokens.css"])
        js = (self.dir / lint.STYLELINT_FILE).read_text(encoding="utf-8")
        self.assertIn('overrides: [{ files: ["src/tokens.css"]', js)

    def test_tailwind_theme_resets_namespaces(self):
        run([str(self.design), "--tailwind", "--tailwind-entry", "src/app.css"])
        css = (self.dir / lint.THEME_FILE).read_text(encoding="utf-8")
        self.assertIn("@theme inline reference {", css)
        self.assertIn("--color-*: initial;", css)
        self.assertIn("--color-primary: var(--primary);", css)
        self.assertIn("--font-jp: var(--font-family-jp);", css)
        self.assertIn("--text-body: var(--font-size-body);", css)
        self.assertIn("--spacing: initial;", css)
        self.assertIn("--spacing-sm: var(--space-sm);", css)
        self.assertIn("--radius: var(--radius);", css)
        eslint = (self.dir / lint.ESLINT_FILE).read_text(encoding="utf-8")
        self.assertIn('entryPoint: "src/app.css"', eslint)

    def test_arbitrary_pattern(self):
        import re
        pat = re.compile(lint.ARBITRARY_PATTERN)
        for cls in ("bg-[#fff]", "md:p-[13px]", "hover:text-[var(--x)]", "rounded-t-[3px]", "-mt-[2px]"):
            self.assertTrue(pat.match(cls), cls)
        for cls in ("bg-primary", "p-sm", "grid-cols-[1fr_2fr]", "w-[320px]"):
            self.assertFalse(pat.match(cls), cls)

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
        self.assertFalse((self.dir / lint.STYLELINT_FILE).exists())

    def test_does_not_overwrite_hand_written_file(self):
        target = self.dir / lint.STYLELINT_FILE
        target.write_text("export default {};\n", encoding="utf-8")
        code, out, _ = run([str(self.design)])
        self.assertEqual(code, 1)
        self.assertIn("skipped-not-generated", out)
        self.assertEqual(target.read_text(encoding="utf-8"), "export default {};\n")

    def test_rejects_paths_outside_out(self):
        code, _, err = run([str(self.design), "--token-file", "../x.css"])
        self.assertEqual(code, 2)
        self.assertIn("相対 path", err)

    def test_no_tokens_is_error(self):
        self.design.write_text("# Design\n\n```css\n.a { color: red; }\n```\n", encoding="utf-8")
        self.assertEqual(run([str(self.design)])[0], 2)


if __name__ == "__main__":
    unittest.main()
