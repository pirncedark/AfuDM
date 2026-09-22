"""Paylasim modal kapatma dugmeleri icin Playwright regresyon testi."""
import os
import re
import unittest
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]


class ModalKapatTest(unittest.TestCase):
    def test_paylasim_modallari_pencere_kontrol_siniflarini_kullanmaz(self):
        html = (ROOT / "ui/index.html").read_text(encoding="utf-8")
        self.assertNotRegex(
            html,
            r'<button class="wc-btn wc-close" data-close="share(?:Center)?Veil"',
        )
        self.assertIn('data-i18n="share.centerTitle"', html)
        self.assertEqual(html.count('data-i18n="share.title"'), 1)
        self.assertNotRegex(html, r'<button[^>]*class="[^"]*wc-[^"]*"[^>]*data-close=')

    def test_paylasim_modallari_x_kapat_ve_escape_ile_kapanir(self):
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                channel=os.environ.get("AFUDM_TEST_BROWSER", "msedge"), headless=True
            )
            page = browser.new_page()
            page.add_init_script("""
                window.fakeBackendState = {
                  items: [], settings: {language: "tr"},
                  stat: {downloadSpeed: 0, uploadSpeed: 0, numActive: 0, numWaiting: 0, numStopped: 0},
                  engine_ok: true, port_status: {calisan: 6811}, lang: "tr"
                };
                window.pywebview = {api: {
                  snapshot: async () => window.fakeBackendState,
                  port_durumu: async () => ({calisan: 6811}), api_info: async () => ({port: 6811}),
                  motor_durumu: async () => ({motorlar: {}, ilerleme: {}}),
                  reliability_integrity: async () => "OK", telefon_durumu: async () => ({acik: false, adres: ""}),
                  share_list: async () => ({ok: true, shares: []})
                }};
            """)
            page.goto((ROOT / "ui/index.html").as_uri())
            page.evaluate("window.dispatchEvent(new Event('pywebviewready'))")
            page.wait_for_function("state.ready === true")

            page.locator("#openShare").click()
            center_veil = page.locator("#shareCenterVeil")
            expect(center_veil).to_have_class(re.compile(r"\bon\b"))
            center_veil.locator("[data-close]").first.click()
            expect(center_veil).not_to_have_class(re.compile(r"\bon\b"))

            for veil_id in ("shareVeil",):
                veil = page.locator(f"#{veil_id}")
                page.evaluate("id => openVeil(id)", veil_id)
                expect(veil).to_have_class(re.compile(r"\bopen\b"))
                page.evaluate("""id => {
                    const oldButton = document.querySelector(`#${id} [data-close]`);
                    oldButton.replaceWith(oldButton.cloneNode(true));
                }""", veil_id)
                veil.locator("[data-close]").first.click()
                expect(veil).not_to_have_class(re.compile(r"\bopen\b"))

                page.evaluate("id => openVeil(id)", veil_id)
                page.keyboard.press("Escape")
                expect(veil).not_to_have_class(re.compile(r"\bopen\b"))

            browser.close()


if __name__ == "__main__":
    unittest.main()
