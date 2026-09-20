import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright, expect

# Playwright UI/UX Gate for AfuDM
# Covers P0 constraints defined in docs/UI_UX_MASTER_TESTLIST.md

class UIUXGateTest(unittest.TestCase):
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
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        
        # We use a fake pywebview to simulate the backend.
        self.page.add_init_script("""
            window.fakeBackendState = {
                items: [],
                settings: { language: "auto", max_concurrent: 5, split: 64, max_conn_per_server: 16 },
                stat: { downloadSpeed: 0, uploadSpeed: 0, numActive: 0, numWaiting: 0, numStopped: 0 },
                engine_ok: true,
                port_status: { calisan: 6811, yeniden_baslatma_gerekli: false },
                download_dir: "C:\\\\Downloads",
                lang: "tr",
                last_error: ""
            };
            
            window.pywebview = {
                api: {
                    snapshot: async () => {
                        if (!window.fakeBackendState.engine_ok) throw new Error("bridge not ready");
                        return window.fakeBackendState;
                    },
                    port_durumu: async () => window.fakeBackendState.port_status,
                    api_info: async () => ({ port: 6811 }),
                    motor_durumu: async () => ({ motorlar: {}, ilerleme: {} }),
                    reliability_integrity: async () => "OK",
                    telefon_durumu: async () => ({ acik: false, adres: "" }),
                    seed_dosyalari: async () => ({ eklenebilir: [], uygulanan: [] }),
                    pencere_kucult: async () => null,
                    pencere_buyut: async () => null,
                    pencere_kapat: async () => null,
                    pencere_kenar: async () => null
                }
            };
        """)
        self.page.goto((Path(__file__).resolve().parents[1] / "ui/index.html").as_uri())
        
        # Now that app.js is loaded, dispatch the event
        self.page.evaluate('window.dispatchEvent(new Event("pywebviewready"));')
        
        # Wait for the app to initialize (tick is called, UI is drawn)
        self.page.wait_for_function("typeof state !== 'undefined' && state.ready === true", timeout=2000)

    def tearDown(self):
        self.page.close()

    def test_g001_to_g004_base_health(self):
        """G-001 to G-004: App opens, no blank screen, no JS errors, DOM valid."""
        expect(self.page.locator("body")).to_be_visible()
        self.assertEqual(len(self.errors), 0, f"Uncaught JS errors found: {self.errors}")
        
        # Check for unclosed tags by seeing if fundamental elements exist
        expect(self.page.locator("#list")).to_be_visible()
        expect(self.page.locator(".rail")).to_be_visible()

    def test_g005_g006_click_everything(self):
        """G-005, G-006: All primary buttons are clickable and don't throw errors."""
        buttons_to_test = [
            "#addBtn", "#lgBtn", "#pauseAll", "#resumeAll", "#clearDone",
            "#openSettings", "[data-f='video']"
        ]
        
        for btn in buttons_to_test:
            el = self.page.locator(btn)
            if el.is_visible():
                el.click(force=True)
                
        # Close any modals that opened
        self.page.keyboard.press("Escape")
        self.page.keyboard.press("Escape")
        
        self.assertEqual(len(self.errors), 0, f"Errors after clicking buttons: {self.errors}")

    def test_g005_g006_all_visible_controls(self):
        """Every initially visible interactive control accepts a real click without an uncaught error."""
        selectors = self.page.locator(
            "button:visible, a:visible, input:visible, select:visible, "
            "[role=tab]:visible, [role=menuitem]:visible"
        )
        for index in range(selectors.count()):
            control = selectors.nth(index)
            if control.is_disabled():
                continue
            control.click(force=True)
            self.page.keyboard.press("Escape")

        self.assertEqual(self.errors, [], f"Uncaught errors after visible controls: {self.errors}")

    def test_g007_to_g010_modal_lifecycle(self):
        """G-007 to G-010: Modal opens, focus traps (implicit), closes with Esc and Backdrop."""
        # 1. Open Add Link Modal
        self.page.locator("#addBtn").click()
        veil = self.page.locator("#addVeil")
        expect(veil).to_be_visible()
        
        # 2. Check Esc closes it
        self.page.keyboard.press("Escape")
        expect(veil).to_be_hidden()
        
        # 3. Open Settings Modal and verify the opening control is restored after closing.
        opener = self.page.locator("#openSettings")
        opener.focus()
        opener.click()
        set_veil = self.page.locator("#setVeil")
        expect(set_veil).to_be_visible()

        # The settings form must contain every control openSettings populates.
        for selector in ["#sVideoDosyaSablonu", "#sVideoTarayiciCerezi"]:
            expect(set_veil.locator(selector)).to_be_visible()

        # 4. Close button closes and returns focus to the opener.
        set_veil.locator('[data-close="setVeil"]').click()
        expect(set_veil).to_be_hidden()
        expect(opener).to_be_focused()

        # 5. Reopen and check Esc.
        opener.click()
        expect(set_veil).to_be_visible()
        self.page.keyboard.press("Escape")
        expect(set_veil).to_be_hidden()

        # 6. Reopen and check the backdrop.
        opener.click()
        expect(set_veil).to_be_visible()
        # Click in the top left corner (0,0) of the veil which is the backdrop
        set_veil.click(position={"x": 5, "y": 5})
        expect(set_veil).to_be_hidden()

    def test_g011_to_g013_engine_offline_recovery(self):
        """G-011 to G-013: UI handles engine death and recovery gracefully."""
        # Make engine offline
        self.page.evaluate("window.fakeBackendState.engine_ok = false")
        
        # Wait for polling to notice
        expect(self.page.locator("#engineText")).to_contain_text("bağlantı yok", timeout=3000)
        expect(self.page.locator("#engineRetry")).to_be_visible()
        
        # A controlled fake backend response keeps the bridge contract async without
        # throwing inside Playwright's evaluation context.
        self.page.evaluate("window.fakeBackendState.port_status = { calisan: null, yeniden_baslatma_gerekli: false }")
        self.page.locator("#openSettings").click()
        
        # Veil should still open even if port check fails
        expect(self.page.locator("#setVeil")).to_be_visible()
        self.page.keyboard.press("Escape")
        
        # Recover engine
        self.page.evaluate("window.fakeBackendState.engine_ok = true")
        self.page.locator("#engineRetry").click()
        
        # Wait for recovery
        expect(self.page.locator("#engineText")).not_to_contain_text("bağlantı yok", timeout=3000)

    def test_g014_reload_reinitializes_without_errors(self):
        """Reloading the UI restores the ready state without leaving a broken screen."""
        self.page.reload()
        self.page.evaluate('window.dispatchEvent(new Event("pywebviewready"));')
        self.page.wait_for_function("typeof state !== 'undefined' && state.ready === true", timeout=2000)
        expect(self.page.locator("#list")).to_be_visible()
        self.assertEqual(self.errors, [])

    def test_g015_language_switch(self):
        """G-015: TR and EN interfaces both render correctly."""
        # Default is TR
        expect(self.page.locator("#addBtn")).to_contain_text("Link ekle")
        
        # Switch to EN via backend state
        self.page.evaluate("window.fakeBackendState.lang = 'en'")
        # Wait for next tick
        expect(self.page.locator("#addBtn")).to_contain_text("Add link", timeout=2000)
        
        # Switch back to TR
        self.page.evaluate("window.fakeBackendState.lang = 'tr'")
        expect(self.page.locator("#addBtn")).to_contain_text("Link ekle", timeout=2000)

    def test_g015_translation_keys_exist_in_tr_and_en(self):
        """Static UI translation references must resolve in both supported languages."""
        missing = self.page.evaluate("""() => {
            const attrs = ["data-i18n", "data-i18n-ph", "data-i18n-title", "data-i18n-html"];
            const keys = new Set();
            for (const attr of attrs) {
                document.querySelectorAll(`[${attr}]`).forEach(node => keys.add(node.getAttribute(attr)));
            }
            const missing = {};
            for (const lang of ["tr", "en"]) {
                missing[lang] = [...keys].filter(key => DICT[lang][key] === undefined);
            }
            return missing;
        }""")
        self.assertEqual(missing, {"tr": [], "en": []}, f"Missing translations: {missing}")

    def test_responsive_and_dpi(self):
        """Viewport resizing does not break layout."""
        viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1280, "height": 720},
            {"width": 1366, "height": 768}
        ]
        
        for vp in viewports:
            self.page.set_viewport_size(vp)
            expect(self.page.locator(".rail")).to_be_visible()
            expect(self.page.locator(".main")).to_be_visible()
            
            # Toolbar buttons should remain inside viewport (no horizontal scroll)
            bb = self.page.locator("#addBtn").bounding_box()
            self.assertLess(bb["x"] + bb["width"], vp["width"])

    def test_responsive_dpi_scales(self):
        """Toolbar remains usable at the Windows DPI scales used by the release gate."""
        for scale in (1.25, 1.5, 2):
            with self.subTest(scale=scale):
                context = self.browser.new_context(
                    viewport={"width": 1280, "height": 720}, device_scale_factor=scale
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.add_init_script("""
                    window.pywebview = { api: {
                        snapshot: async () => ({ items: [], settings: {}, stat: {}, engine_ok: true, lang: "tr" }),
                        port_durumu: async () => ({ calisan: 6811 }), api_info: async () => ({ port: 6811 }),
                        motor_durumu: async () => ({ motorlar: {}, ilerleme: {} }), reliability_integrity: async () => "OK",
                        telefon_durumu: async () => ({ acik: false, adres: "" }), seed_dosyalari: async () => ({ eklenebilir: [], uygulanan: [] })
                    }};
                """)
                page.goto((Path(__file__).resolve().parents[1] / "ui/index.html").as_uri())
                page.evaluate('window.dispatchEvent(new Event("pywebviewready"));')
                page.wait_for_function("typeof state !== 'undefined' && state.ready === true", timeout=2000)
                box = page.locator("#addBtn").bounding_box()
                self.assertLessEqual(box["x"] + box["width"], 1280)
                self.assertEqual(errors, [])
                context.close()

if __name__ == "__main__":
    unittest.main()
