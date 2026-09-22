"""Pencere boyutu ve ozel baslik dugmeleri icin GUI'siz regresyon testi."""
from pathlib import Path
import ast
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PencereDugmeTest(unittest.TestCase):
    def test_api_kopruleri_mevcut_ve_dogru_cagirir(self):
        tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        api = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Api")
        methods = {n.name: n for n in api.body if isinstance(n, ast.FunctionDef)}
        for name in ("pencere_kucult", "pencere_buyut", "pencere_kapat", "pencere_durumu"):
            self.assertIn(name, methods)
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("self._window.minimize()", source)
        self.assertIn("self._window.maximize()", source)
        self.assertIn("self._window.destroy()", source)

    def test_ui_dugmeleri_bridgee_bagli(self):
        html = (ROOT / "ui/index.html").read_text(encoding="utf-8")
        js = (ROOT / "ui/app.js").read_text(encoding="utf-8")
        css = (ROOT / "ui/style.css").read_text(encoding="utf-8")
        for ident in ("wcMin", "wcMax", "wcClose"):
            self.assertRegex(html, rf'id="{ident}"')
        self.assertIn("pencere_kucult", js)
        self.assertIn("pencere_buyut", js)
        self.assertIn("pencere_kapat", js)
        self.assertIn("-webkit-app-region: no-drag", css)

    def test_pencere_boyutu_sinirlar(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("EnumDisplayMonitors", source)
        self.assertIn("GetDpiForSystem", source)
        self.assertIn("min(min_hedef_w, wa_w)", source)
        self.assertIn("min(min_hedef_h, wa_h)", source)


if __name__ == "__main__":
    unittest.main()
