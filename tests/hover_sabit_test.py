import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright, expect


class HoverSabitTest(unittest.TestCase):
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
        self.page.add_init_script(
            """
            window.fakeBackendState = {
                items: [{
                    gid: "hover-video-1", id: "hover-video-1", title: "bitmis video",
                    kind: "video", status: "complete", progress: 100,
                    completedLength: 1048576, totalLength: 1048576,
                    downloadSpeed: 0, uploadSpeed: 0, eta: 0, connections: 0,
                    numSeeders: 0, dir: "C:\\\\Downloads"
                }],
                settings: {language: "auto", max_concurrent: 5, split: 64, max_conn_per_server: 16},
                stat: {downloadSpeed: 0, uploadSpeed: 0, numActive: 0, numWaiting: 0},
                engine_ok: true, port_status: {calisan: 6811, yeniden_baslatma_gerekli: false},
                download_dir: "C:\\\\Downloads", lang: "tr", last_error: ""
            };
            window.pywebview = {api: {
                snapshot: async () => window.fakeBackendState,
                api_info: async () => ({port: 6811}),
                surum_bilgi: async () => ({surum: "2.4.0"}),
                motor_durumu: async () => ({motorlar: {}, ilerleme: {}}),
                rules_list: async () => ({rules: []}),
                reliability_integrity: async () => "OK",
                reliability_restart_engine: async () => ({ok: true}),
                telefon_durumu: async () => ({acik: false, adres: ""}),
                seed_dosyalari: async () => ({eklenebilir: [], uygulanan: []})
            }};
            """
        )
        self.page.goto((Path(__file__).resolve().parents[1] / "ui/index.html").as_uri())
        self.page.evaluate("window.dispatchEvent(new Event('pywebviewready'))")
        row = self.page.locator("#list .row")
        expect(row).to_be_visible(timeout=3000)

    def tearDown(self):
        self.page.close()

    def test_satir_ve_eylem_dugmesi_hoverda_yer_degistirmez(self):
        row = self.page.locator("#list .row")
        button = row.locator('button[data-act="open"]')
        before = row.bounding_box()
        button_before = button.bounding_box()

        row.hover()
        button.hover()

        after = row.bounding_box()
        button_after = button.bounding_box()
        for field in ("x", "y", "width", "height"):
            self.assertAlmostEqual(before[field], after[field], places=6, msg=f"satir {field} degisti")
            self.assertAlmostEqual(button_before[field], button_after[field], places=6, msg=f"dugme {field} degisti")


if __name__ == "__main__":
    unittest.main()
