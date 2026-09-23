# -*- coding: utf-8 -*-
"""Köprü eşleme testi (tests/kopru_esleme_test.py).

ui/app.js icinden çağrılan HER BİR bridge fonksiyon adının (call("..."),
dinamik windows_integration_* öneki ve doğrudan pywebview.api.* çağrıları)
app.py icindeki `Api` sınıfında bir karşılığı olmak ZORUNDADIR.

Eksik isim = çalışma anında "Not a function" hatası demektir; bu test böyle
bir adayı daha derleme/diagnostik aşamasında yakalar. Kaynaklara hiç dokunmaz
(salt-okuma); yalnızca isimleri karşılaştırır.
"""
import ast
import re
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]


def api_yontemleri():
    """app.py icindeki `Api` sınıfının metod adları (statik AST ile)."""
    agac = ast.parse((KOK / "app.py").read_text(encoding="utf-8"))
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.ClassDef) and dugum.name == "Api":
            return {
                g.name
                for g in dugum.body
                if isinstance(g, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return set()


def appjs_bridge_isimleri():
    """app.js'te call("ad") ile çağrılan isimler.

    Dinamik istisnalar: windows_integration_* + data-winint değerleri ile
    çalışma anında birleştirilir; her üç kombinasyon da teker teker denenir.
    """
    src = (KOK / "ui" / "app.js").read_text(encoding="utf-8")
    statik = set(
        re.findall(r"call\(\s*[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']", src)
    ) - {"windows_integration_"}
    dinamik = {
        "windows_integration_" + v
        for v in re.findall(r"data-winint=\"([A-Za-z0-9_]+)\"", src)
    }
    return statik | dinamik


def appjs_pywebview_dogrudan():
    """uygulamanın köprüden direkt (call() harici) çağırdığı api adları."""
    src = (KOK / "ui" / "app.js").read_text(encoding="utf-8")
    return set(
        re.findall(r"pywebview\??\.api\.([A-Za-z_][A-Za-z0-9_]*)", src)
    )


class KopruEslemeTest(unittest.TestCase):
    def test_api_sinifi_var(self):
        yontemler = api_yontemleri()
        self.assertTrue(
            yontemler, "app.py icinde 'Api' sinifi bulunamadi (name degisti mi?)"
        )

    def test_appjs_call_isimleri_api_de_var(self):
        eksik = sorted(appjs_bridge_isimleri() - api_yontemleri())
        self.assertEqual(
            [],
            eksik,
            "ui/app.js'te call(\"...\") ile çağrılan köprü adları app.py Api "
            "sınıfında YOK: %s" % eksik,
        )

    def test_pywebview_dogrudan_cagrilar_api_de_var(self):
        eksik = sorted(appjs_pywebview_dogrudan() - api_yontemleri())
        self.assertEqual(
            [],
            eksik,
            "app.js'ten doğrudan pywebview.api.* ile çağrılan adlar app.py Api "
            "sınıfında YOK: %s" % eksik,
        )


if __name__ == "__main__":
    unittest.main()