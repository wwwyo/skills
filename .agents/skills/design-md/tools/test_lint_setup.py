"""lint-setup.py の unittest。

生成した設定を実際の stylelint / ESLint で通す検証は node が要るため README の手順で行い、
ここでは token の分類・許可値の正規表現・--check の判定を確かめる。
"""

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_common import md_to_css  # noqa: E402

_spec = importlib.util.spec_from_file_location("lint_setup", Path(__file__).parent / "lint-setup.py")
ls = importlib.util.module_from_spec(_spec)
sys.modules["lint_setup"] = ls
_spec.loader.exec_module(ls)

SPEC_MD = """# Design — test

## Tokens

```css
:root {
  --primary: #1b6e5c;
  --primary-foreground: #ffffff;
  --brand: oklch(60% 0.1 30);
  --space-sm: 8px;
  --space-md: 16px;
  --radius: 6px;
  --font-size-body: 15px;
  --font-family-jp: "Noto Sans JP", sans-serif;
  --duration-fast: 120ms;
  --sidebar-width: 240px;
}
```

## Components

```css
.btn { padding: 10px 20px; border-radius: var(--radius); }
```
"""


def js_regex(pattern: str) -> re.Pattern:
    """stylelint の "/.../" 文字列を Python の正規表現にする（使う構文は両者で共通）。"""
    return re.compile(pattern[1:-1])


class ClassifyTest(unittest.TestCase):
    def test_categories(self):
        tokens, _ = ls.parse_design(md_to_css(SPEC_MD))
        self.assertEqual(tokens["--primary"], "color")
        self.assertEqual(tokens["--brand"], "color")
        self.assertEqual(tokens["--space-md"], "spacing")
        self.assertEqual(tokens["--radius"], "radius")
        self.assertEqual(tokens["--font-size-body"], "font-size")
        self.assertEqual(tokens["--font-family-jp"], "font-family")
        self.assertEqual(tokens["--duration-fast"], "duration")
        self.assertEqual(tokens["--sidebar-width"], "")

    def test_component_literals_are_allowed(self):
        _, literals = ls.parse_design(md_to_css(SPEC_MD))
        self.assertEqual(literals["spacing"], {"10px", "20px"})


class StylelintConfigTest(unittest.TestCase):
    def setUp(self):
        tokens, literals = ls.parse_design(md_to_css(SPEC_MD))
        self.config = ls.build_stylelint(tokens, literals, ["src/tokens.css"])
        self.allowed = self.config["rules"]["declaration-property-value-allowed-list"][0]

    def pattern_for(self, prop: str) -> re.Pattern:
        for key, (value,) in self.allowed.items():
            if js_regex(key).search(prop):
                return js_regex(value)
        self.fail(f"{prop} の許可値が無い")

    def test_spacing_accepts_tokens_and_design_literals(self):
        p = self.pattern_for("padding")
        for ok in ["var(--space-sm) var(--space-md)", "10px 20px", "0 auto", "calc(var(--space-md) * -1)", "var(--sidebar-width)"]:
            self.assertTrue(p.search(ok), ok)
        for bad in ["13px", "calc(13px + var(--space-md))", "var(--unknown)"]:
            self.assertFalse(p.search(bad), bad)

    def test_color_accepts_only_color_tokens(self):
        p = self.pattern_for("background-color")
        self.assertTrue(p.search("var(--primary)"))
        self.assertTrue(p.search("transparent"))
        self.assertFalse(p.search("var(--space-md)"))
        self.assertFalse(p.search("var(--sidebar-width)"))

    def test_undefined_category_is_not_constrained(self):
        self.assertFalse(any(js_regex(k).search("line-height") for k in self.allowed))

    def test_exports_are_exempt(self):
        override = self.config["overrides"][0]
        self.assertEqual(override["files"], ["src/tokens.css"])
        self.assertIsNone(override["rules"]["color-no-hex"])

    def test_motion_shorthand_disallows_literal_duration(self):
        disallowed = self.config["rules"]["declaration-property-value-disallowed-list"][0]
        (dur,) = disallowed["/^(transition|animation)$/"]
        self.assertTrue(js_regex(dur).search("opacity 200ms ease"))
        self.assertFalse(js_regex(dur).search("opacity var(--duration-fast) ease"))


class EslintConfigTest(unittest.TestCase):
    def test_tailwind_rules_only_with_entry(self):
        tokens, _ = ls.parse_design(md_to_css(SPEC_MD))
        self.assertEqual(len(ls.build_eslint(tokens, None)), 1)
        configs = ls.build_eslint(tokens, "src/global.css")
        self.assertEqual(configs[1]["settings"]["better-tailwindcss"]["entryPoint"], "src/global.css")

    def test_palette_restriction_regex(self):
        tokens, _ = ls.parse_design(md_to_css(SPEC_MD))
        restrict = ls.build_eslint(tokens, "src/global.css")[1]["rules"]["better-tailwindcss/no-restricted-classes"][1]["restrict"]
        arbitrary, palette = (re.compile(r["pattern"]) for r in restrict)
        self.assertTrue(arbitrary.search("bg-[#fff]"))
        self.assertTrue(palette.search("hover:bg-slate-100/50"))
        self.assertFalse(palette.search("bg-primary"))


class CliTest(unittest.TestCase):
    def run_cli(self, *args: str) -> int:
        return ls.main(list(args))

    def test_check_detects_stale_output(self):
        with tempfile.TemporaryDirectory() as d:
            spec = Path(d) / "design.md"
            spec.write_text(SPEC_MD, encoding="utf-8")
            self.assertEqual(self.run_cli(str(spec), "--check", "--json"), 1)  # missing
            self.assertEqual(self.run_cli(str(spec), "--json"), 0)
            self.assertEqual(self.run_cli(str(spec), "--check", "--json"), 0)
            spec.write_text(SPEC_MD.replace("10px 20px", "12px 20px"), encoding="utf-8")
            self.assertEqual(self.run_cli(str(spec), "--check", "--json"), 1)  # stale

    def test_rejects_unknown_target(self):
        with tempfile.TemporaryDirectory() as d:
            spec = Path(d) / "design.md"
            spec.write_text(SPEC_MD, encoding="utf-8")
            self.assertEqual(self.run_cli(str(spec), "--targets", "prettier"), 2)


if __name__ == "__main__":
    unittest.main()
