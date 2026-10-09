import os
import re
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
        viewport = os.environ.get("AFUDM_TEST_VIEWPORT", "1280x720")
        try:
            cls.test_width, cls.test_height = (int(value) for value in viewport.split("x", 1))
        except ValueError as exc:
            raise unittest.SkipTest(f"Geçersiz AFUDM_TEST_VIEWPORT: {viewport}") from exc
        try:
            cls.test_dpr = float(os.environ.get("AFUDM_TEST_DPR", "1"))
        except ValueError as exc:
            raise unittest.SkipTest("Geçersiz AFUDM_TEST_DPR") from exc
        cls.test_lang = os.environ.get("AFUDM_TEST_LANG", "tr")
        if cls.test_lang not in {"tr", "en"}:
            raise unittest.SkipTest(f"Geçersiz AFUDM_TEST_LANG: {cls.test_lang}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(
            viewport={"width": self.test_width, "height": self.test_height},
            device_scale_factor=self.test_dpr,
        )
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on(
            "console",
            lambda message: self.errors.append(f"console.error: {message.text}")
            if message.type == "error"
            else None,
        )

        # We use a fake pywebview to simulate the backend.
        self.page.add_init_script("""
            window.fakeBackendState = {
                items: [],
                settings: { language: "auto", max_concurrent: 5, split: 64, max_conn_per_server: 16 },
                stat: { downloadSpeed: 0, uploadSpeed: 0, numActive: 0, numWaiting: 0, numStopped: 0 },
                engine_ok: true,
                port_status: { calisan: 6811, yeniden_baslatma_gerekli: false },
                download_dir: "C:\\\\Downloads",
                lang: "LANGUAGE",
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
                    rules_list: async () => ({ rules: [] }),
                    surum_bilgi: async () => ({ surum: "2.9.1", uzanti: "2.9.1" }),
                    motor_durumu: async () => ({ motorlar: {}, ilerleme: {} }),
                    reliability_integrity: async () => "OK",
                    reliability_restart_engine: async () => ({ ok: window.fakeBackendState.engine_ok, message: "motor yeniden baslatildi" }),
                    telefon_durumu: async () => ({ acik: false, adres: "" }),
                    seed_dosyalari: async () => ({ eklenebilir: [], uygulanan: [] }),
                    pencere_kucult: async () => null,
                    pencere_buyut: async () => null,
                    pencere_kapat: async () => null,
                    pencere_kenar: async () => null,
                    share_create: async () => ({ token: "fakeToken", url: "http://127.0.0.1/s/fakeToken" }),
                    share_list: async () => ({ ok: true, shares: [] }),
                    share_delete: async () => ({ ok: true })
                }
            };
        """.replace("LANGUAGE", self.test_lang))
        self.page.goto((Path(__file__).resolve().parents[1] / "ui/index.html").as_uri())

        # Now that app.js is loaded, dispatch the event
        self.page.evaluate('window.dispatchEvent(new Event("pywebviewready"));')

        # Wait for the app to initialize (tick is called, UI is drawn)
        self.page.wait_for_function("typeof state !== 'undefined' && state.ready === true", timeout=2000)

    def tearDown(self):
        self.context.close()

    def test_g001_to_g004_base_health(self):
        """G-001 to G-004: App opens, no blank screen, no JS errors, DOM valid."""
        expect(self.page.locator("body")).to_be_visible()
        self.assertEqual(len(self.errors), 0, f"Uncaught JS errors found: {self.errors}")

        # Check for unclosed tags by seeing if fundamental elements exist
        expect(self.page.locator("#list")).to_be_visible()
        expect(self.page.locator(".rail")).to_be_visible()

    def test_auto_update_downloads_cached_release_and_waits_for_idle(self):
        result = self.page.evaluate("""async () => {
            const events = [];
            const api = window.pywebview.api;
            api.guncelleme_son_kontrol = async () => ({aktif:true, paketli:true,
                zaman:Date.now()/1000, bilgi:{ok:true,var:true,yeni:'2.10.0'}});
            api.guncelleme_kontrol = async () => { throw new Error('cached check should be reused'); };
            api.guncelleme_indir = async b => { events.push('download:' + b.yeni); return {ok:true}; };
            api.guncelleme_durum = async () => ({durum:'bitti'});
            api.guncelleme_uygula = async automatic => {
                events.push('apply:' + automatic);
                return events.filter(x => x.startsWith('apply:')).length === 1
                    ? {ok:true,bekle:true} : {ok:true};
            };
            const delay = window.setTimeout;
            window.setTimeout = (f, ms, ...args) => delay(f, ms >= 2000 ? 0 : ms, ...args);
            try { await guncellemeOtomatikKontrol(); } finally { window.setTimeout = delay; }
            return events;
        }""")
        self.assertEqual(result, ['download:2.10.0', 'apply:true', 'apply:true'])
        self.assertEqual(self.errors, [])

    def test_auto_update_opt_out_does_not_download(self):
        result = self.page.evaluate("""async () => {
            let downloads = 0;
            window.pywebview.api.guncelleme_son_kontrol = async () => ({aktif:false,paketli:true});
            window.pywebview.api.guncelleme_indir = async () => { downloads++; return {ok:true}; };
            await guncellemeOtomatikKontrol();
            return downloads;
        }""")
        self.assertEqual(result, 0)
        self.assertEqual(self.errors, [])

    def test_update_rejected_download_stops_without_apply(self):
        result = self.page.evaluate("""async () => {
            let applied = false;
            guncellemeBilgisi = {ok:true,var:true,yeni:'2.10.0'};
            window.pywebview.api.guncelleme_indir = async () => ({ok:false,hata:'download rejected'});
            window.pywebview.api.guncelleme_durum = async () => ({durum:'bitti'});
            window.pywebview.api.guncelleme_uygula = async () => {applied=true; return {ok:true};};
            await guncellemeBaslat(false);
            return {applied, locked:guncellemeIsliyor, disabled:document.getElementById('guncellemeBtn').disabled};
        }""")
        self.assertEqual(result, {'applied': False, 'locked': False, 'disabled': False})
        self.assertEqual(self.errors, [])

    def test_share_filename_is_rendered_as_text_without_script_execution(self):
        self.page.evaluate("""() => {
            window.__xss = undefined;
            window.pywebview.api.share_list = async () => ({ok: true, shares: [{
              filename: '<img src=x onerror=window.__xss=1>',
              url: 'http://127.0.0.1/s/test', token: 'test'
            }]});
        }""")
        self.page.locator("#openShare").click()
        expect(self.page.locator("#shareList")).to_contain_text("<img src=x onerror=window.__xss=1>")
        self.assertEqual(self.page.evaluate("window.__xss"), None)
        self.assertEqual(self.page.locator("#shareList img").count(), 0)

    def test_pause_button_updates_immediately_and_reverts_on_failure(self):
        """Duraklatma UI'si gecikmeli backend'i beklemeden değişir ve hata halinde geri döner."""
        self.page.evaluate("""() => {
            window.fakeBackendState.items = [{gid: "slow-gid", id: 1, title: "Paylasiliyor",
              kind: "torrent", status: "active", seeder: true, progress: 100,
              completedLength: 100, totalLength: 100, downloadSpeed: 0,
              connections: 0, numSeeders: 1, eta: 0}];
            state.items = window.fakeBackendState.items;
            renderList();
            window.pauseBackend = () => new Promise(resolve => setTimeout(() => {
              window.fakeBackendState.items[0].status = "paused";
              resolve({ok: true});
            }, 450));
            window.pywebview.api.control = (...args) => window.pauseBackend(...args);
        }""")

        elapsed = self.page.evaluate("""() => {
            const button = document.querySelector('[data-act="pause"][data-gid="slow-gid"]');
            const started = performance.now();
            button.click();
            return performance.now() - started;
        }""")
        expect(self.page.locator('[data-act="resume"][data-gid="slow-gid"]')).to_be_visible(timeout=150)
        expect(self.page.locator('[data-act="resume"][data-gid="slow-gid"]')).to_be_disabled()
        self.assertLess(elapsed, 150, f"UI degisimi {elapsed:.1f} ms surdu")

        expect(self.page.locator('[data-act="resume"][data-gid="slow-gid"]')).to_be_visible(timeout=2000)
        self.page.evaluate("""() => { window.pywebview.api.control = () => new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Motor yanit vermedi')), 450)); }""")
        self.page.locator('[data-act="resume"][data-gid="slow-gid"]').click()
        expect(self.page.locator('[data-act="pause"][data-gid="slow-gid"]')).to_be_visible(timeout=150)
        expect(self.page.locator('[data-act="resume"][data-gid="slow-gid"]')).to_be_visible(timeout=2000)
        expect(self.page.locator("#toast")).to_contain_text("Başlatılamadı. Yeniden deneyin.")

    def test_mobile_page_script_parses_clean(self):
        """Mobil arayuz (mobil.html) scripti hatasiz yuklenmeli.

        Gecmiste inline script 'trackerTara' dinleyicisi '});' yerine '}' ile
        bitince TUM script parse edilemiyordu: sayfa statik HTML ile aciliyor
        ama hicbir JS calismiyor, 'aciliyor ama baglanmiyor' gorunumu olu-
        syordu. Sayfa yuklenirken pageerror olmamasi bu sinifi yakalar."""
        mobil = Path(__file__).resolve().parents[1] / "ui" / "mobil.html"
        sayfa = self.browser.new_page()
        try:
            hatalar = []
            sayfa.on("pageerror", lambda hata: hatalar.append(str(hata)))
            sayfa.goto(mobil.as_uri())
            sayfa.wait_for_timeout(400)
            self.assertEqual([], hatalar, f"mobil.html script hatalari: {hatalar}")
            expect(sayfa.locator("#baglantiUyari")).to_be_attached()
        finally:
            sayfa.close()

    def test_rules_veil_opens_even_when_bridge_fails(self):
        """rulesOpen her durumda paneli acar; veri yuklenemezse hata panelin icinde.

        Eski derlemede koprude rules_list YOKTU: tiktakta 'rules_list is not a
        function' hatasi atiliyor, catch toast gosteriyor ve openVeil hic cag-
        rilip panel hic acilmiyordu. Panelin acilmasi + hatanin #rulesErr'de
        gorunmesi bu sinifi kilitler."""
        self.page.evaluate("delete window.pywebview.api.rules_list;")
        self.page.locator("#rulesOpen").click(force=True)
        expect(self.page.locator("#rulesVeil")).to_have_class(re.compile(r"\bopen\b"))
        self.page.wait_for_function(
            "document.getElementById('rulesErr').textContent.trim().length > 0",
            timeout=3000,
        )

    def test_g005_g006_click_everything(self):
        """G-005, G-006: All primary buttons are clickable and don't throw errors."""
        buttons_to_test = [
            "#addBtn", "#lgBtn", "#pauseAll", "#resumeAll", "#clearDone",
            "#openSettings", "#rulesOpen", "[data-f='video']"
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

    def test_rules_and_global_version_are_visible(self):
        """Sidebar rules opens its modal and the persistent version indicator is populated."""
        self.page.locator("#rulesOpen").click()
        expect(self.page.locator("#rulesVeil")).to_be_visible()
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#globalModel")).to_contain_text("AfuDM v2.9.1")

    def test_rules_delayed_response_opens_once_then_loads(self):
        self.page.evaluate("""() => {
            window.rulesCalls = 0;
            window.pywebview.api.rules_list = () => {
                window.rulesCalls++;
                return new Promise(resolve => window.finishRules = resolve);
            };
            document.querySelector('#rulesOpen').click();
        }""")
        expect(self.page.locator("#rulesVeil")).to_be_visible(timeout=150)
        self.assertEqual(self.page.locator(".veil.open").count(), 1)
        self.assertEqual(self.page.evaluate("window.rulesCalls"), 1)
        self.page.evaluate("window.finishRules({rules: [{name: 'Test rule', active: true, conditions: [], actions: {}}]})")
        expect(self.page.locator("#rulesList [data-name='0']")).to_have_value("Test rule")
        expect(self.page.locator("#rulesErr")).to_be_empty()

    def test_rules_missing_engine_has_translated_action(self):
        self.page.evaluate("delete window.pywebview.api.rules_list")
        self.page.locator("#rulesOpen").click()
        expect(self.page.locator("#rulesErr")).to_have_text(
            self.page.evaluate("t('rules.engineMissing')"))
        self.assertEqual(self.errors, [])

    def test_rules_missing_bridge_has_translated_error(self):
        self.page.evaluate("""() => {
            const bridge = window.pywebview;
            delete window.pywebview;
            document.querySelector('#rulesOpen').click();
            window.pywebview = bridge;
        }""")
        expect(self.page.locator("#rulesVeil")).to_be_visible()
        expect(self.page.locator("#rulesErr")).to_have_text(self.page.evaluate("t('err.bridge')"))
        self.assertEqual(self.errors, [])

    def test_version_delayed_bridge_failure_and_visible_retry(self):
        self.page.evaluate("""() => {
            surumBilgisi = null;
            document.querySelector('#brandSurum').textContent = '';
            document.querySelector('#globalModel').textContent = '';
            window.pywebview.api.surum_bilgi = () => new Promise(resolve => window.finishVersion = resolve);
            window.dispatchEvent(new Event('pywebviewready'));
        }""")
        expect(self.page.locator("#list")).to_be_visible()
        expect(self.page.locator("#globalModel")).to_be_empty()
        self.page.evaluate("window.finishVersion({surum: '2.9.1', uzanti: '2.9.1'})")
        expect(self.page.locator("#brandSurum")).to_have_text("v2.9.1")
        expect(self.page.locator("#globalModel")).to_have_text("AfuDM v2.9.1")
        self.page.locator("#openSettings").click()
        expect(self.page.locator("#sSurum b")).to_have_text(["2.9.1", "2.9.1"])
        self.page.keyboard.press("Escape")
        self.page.evaluate("""async () => {
            surumBilgisi = null;
            document.querySelector('#brandSurum').textContent = '';
            document.querySelector('#globalModel').textContent = '';
            delete window.pywebview.api.surum_bilgi;
            await surumuYukle();
        }""")
        self.page.locator("#openSettings").click()
        expect(self.page.locator("#sSurum")).to_have_text(self.page.evaluate("t('set.surumYok')"))
        self.page.keyboard.press("Escape")
        self.page.evaluate("window.pywebview.api.surum_bilgi = async () => ({surum: '2.9.1', uzanti: '2.9.1'})")
        self.page.locator("#openSettings").click()
        expect(self.page.locator("#globalModel")).to_have_text("AfuDM v2.9.1")
        expect(self.page.locator("#sSurum b")).to_have_text(["2.9.1", "2.9.1"])
        self.page.keyboard.press("Escape")
        self.page.reload()
        self.page.evaluate("window.dispatchEvent(new Event('pywebviewready'))")
        expect(self.page.locator("#globalModel")).to_have_text("AfuDM v2.9.1")
        self.assertEqual(self.errors, [])

    def test_version_badge_narrow_window_does_not_cover_primary_action(self):
        for width in (640, 800, 1280):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 600})
                badge = self.page.locator("#globalModel")
                expect(badge).to_have_text("AfuDM v2.9.1")
                box = badge.bounding_box()
                button = self.page.locator("#addBtn").bounding_box()
                self.assertLessEqual(box["x"] + box["width"], width)
                self.assertLessEqual(box["y"] + box["height"], 600)
                self.assertTrue(box["y"] >= button["y"] + button["height"] or
                                box["x"] >= button["x"] + button["width"])
                self.assertEqual(badge.evaluate("el => getComputedStyle(el).position"), "fixed")
                self.assertEqual(badge.evaluate("el => getComputedStyle(el).pointerEvents"), "none")

    def test_trace_has_no_divider_below_the_speed_readout(self):
        """The trace/status junction is intentionally seamless."""
        self.assertEqual(
            self.page.locator(".trace").evaluate("el => getComputedStyle(el).borderBottomWidth"),
            "0px",
        )

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

        # Open advanced accordions so their contents are visible
        self.page.evaluate("document.querySelectorAll('.adv-accordion').forEach(el => el.open = true);")

        # The settings form must contain every control openSettings populates.
        set_veil.locator("[data-stab='video']").click()
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

    def test_share_center_modal_lifecycle(self):
        """Paylaşım Merkezi opens, renders the empty state, and closes with Escape."""
        share_veil = self.page.locator("#shareCenterVeil").first
        self.page.locator("#openShare").click()
        expect(share_veil).to_be_visible()
        empty_text = "Henüz paylaşılan bir dosya yok." if self.test_lang == "tr" else "No shared files yet."
        expect(self.page.locator("#shareList")).to_contain_text(empty_text)
        self.page.keyboard.press("Escape")
        expect(share_veil).to_be_hidden()
        self.assertEqual(self.errors, [])

    def test_g011_to_g013_engine_offline_recovery(self):
        """G-011 to G-013: UI handles engine death and recovery gracefully."""
        # Make engine offline
        self.page.evaluate("window.fakeBackendState.engine_ok = false")

        # Wait for polling to notice
        offline_text = "bağlantı yok" if self.test_lang == "tr" else "no connection"
        expect(self.page.locator("#engineText")).to_contain_text(offline_text, timeout=3000)
        expect(self.page.locator("#engineRetry")).to_be_visible()

        # A controlled fake backend response keeps the bridge contract async without
        # throwing inside Playwright's evaluation context.
        self.page.evaluate("window.fakeBackendState.port_status = { calisan: null, yeniden_baslatma_gerekli: false }")
        self.page.locator("#openSettings").click()

        # Veil should still open even if port check fails
        expect(self.page.locator("#setVeil")).to_be_visible()
        self.page.keyboard.press("Escape")

        # Click while the retry control is still visible; the next UI tick hides it
        # as soon as the fake backend reports a recovered engine.
        expect(self.page.locator("#engineRetry")).to_be_visible()
        self.page.locator("#engineRetry").click()
        self.page.evaluate("window.fakeBackendState.engine_ok = true")

        # Wait for recovery
        expect(self.page.locator("#engineText")).not_to_contain_text(offline_text, timeout=3000)

    def test_g014_reload_reinitializes_without_errors(self):
        """Reloading the UI restores the ready state without leaving a broken screen."""
        self.page.reload()
        self.page.evaluate('window.dispatchEvent(new Event("pywebviewready"));')
        self.page.wait_for_function("typeof state !== 'undefined' && state.ready === true", timeout=2000)
        expect(self.page.locator("#list")).to_be_visible()
        self.assertEqual(self.errors, [])

    def test_g015_language_switch(self):
        """G-015: TR and EN interfaces both render correctly."""
        expected = {
            "tr": {"button": "Link ekle", "other": "Add link"},
            "en": {"button": "Add link", "other": "Link ekle"},
        }[self.test_lang]
        expect(self.page.locator("#addBtn")).to_contain_text(expected["button"])

        other_lang = "en" if self.test_lang == "tr" else "tr"
        self.page.evaluate(f"window.fakeBackendState.lang = '{other_lang}'")
        expect(self.page.locator("#addBtn")).to_contain_text(expected["other"], timeout=2000)

        self.page.evaluate(f"window.fakeBackendState.lang = '{self.test_lang}'")
        expect(self.page.locator("#addBtn")).to_contain_text(expected["button"], timeout=2000)

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
        for scale in (1, 1.5, 2):
            with self.subTest(scale=scale):
                context = self.browser.new_context(
                    viewport={"width": 1280, "height": 720}, device_scale_factor=scale
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on(
                    "console",
                    lambda message: errors.append(f"console.error: {message.text}")
                    if message.type == "error"
                    else None,
                )
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
