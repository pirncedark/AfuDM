# -*- coding: utf-8 -*-
"""Headless ayar dogrulama UI regresyon testleri."""
import os
import sys
import unittest
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "tests"))
from panel_dongu_test import _sahte_backend_script  # noqa: E402


class AyarDogrulamaUITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            channel=os.environ.get("AFUDM_TEST_BROWSER", "msedge"), headless=True
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.add_init_script(_sahte_backend_script())
        self.page.goto((KOK / "ui" / "index.html").as_uri())
        self.page.evaluate('window.dispatchEvent(new Event("pywebviewready"));')
        self.page.wait_for_function("state && state.ready === true", timeout=4000)
        self.page.locator("#openSettings").click()
        expect(self.page.locator("#setVeil")).to_have_class("veil open")

    def tearDown(self):
        self.page.close()

    def _save_response(self, response_js):
        self.page.evaluate("window.pywebview.api.ayarlari_dogrula_kaydet = " + response_js)

    def test_invalid_port_shows_network_tab_field_and_message(self):
        self._save_response("async (payload) => ({ok:false, hatalar:[{alan:'api_listen_port', mesaj_anahtari:'err.portRange'}]})")
        self.page.locator("[data-stab='ag']").click()
        self.page.locator(".adv-accordion").last.evaluate("el => el.open = true")
        self.page.locator("#sLanAccess").check()
        self.page.locator("#sApiPort").fill("1")
        self.page.locator("#setGo").click()

        expect(self.page.locator("#sPaneAg")).to_have_class("set-pane active")
        expect(self.page.locator("#sApiPort")).to_be_focused()
        expect(self.page.locator("#sApiPort")).to_have_attribute("aria-invalid", "true")
        self.assertEqual(self.page.locator("#toast").inner_text(), self.page.evaluate("t('err.portRange')"))
        expect(self.page.locator("#setVeil")).to_have_class("veil open")
        self.assertEqual(self.page.locator("#sApiPort").evaluate("el => el.value"), "1")

    def test_general_error_shows_fallback_message_and_keeps_panel_open(self):
        self._save_response("async () => ({ok:false, hatalar:[{alan:'_genel', mesaj_anahtari:'err.invalidValue'}]})")
        self.page.locator("#setGo").click()
        self.assertEqual(self.page.locator("#toast").inner_text(), self.page.evaluate("t('err.invalidValue')"))
        expect(self.page.locator("#setVeil")).to_have_class("veil open")

    def test_valid_save_closes_panel_and_shows_saved_toast(self):
        self._save_response("async () => ({ok:true, ayarlar:{}})")
        self.page.locator("#setGo").click()
        expect(self.page.locator("#setVeil")).not_to_have_class("veil open")
        self.assertEqual(self.page.locator("#toast").inner_text(), self.page.evaluate("t('toast.saved')"))

    def test_other_call_failure_keeps_generic_error_behavior(self):
        self.page.evaluate("window.pywebview.api.clear_finished = async () => ({ok:false})")
        self.page.evaluate("call('clear_finished').catch(err => toast(err.message, true))")
        self.assertEqual(self.page.locator("#toast").inner_text(), self.page.evaluate("t('err.failed')"))


if __name__ == "__main__":
    unittest.main()
