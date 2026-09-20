"""Real HTML/browser regression: malformed markup must not disable the UI.

Run: python tests/ui_startup_test.py
Requires Playwright and Microsoft Edge (AFUDM_TEST_BROWSER can override).
No download engine or user data is accessed.
"""
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright, expect


class UIStartupTest(unittest.TestCase):
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
        self.page = self.browser.new_page(viewport={"width": 914, "height": 592})
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto((Path(__file__).resolve().parents[1] / "ui/index.html").as_uri())

    def tearDown(self):
        self.page.close()

    def test_link_dialog_opens_and_closes_without_engine(self):
        self.page.locator("#addBtn").click()
        expect(self.page.locator("#addVeil")).to_be_visible(timeout=1500)
        self.page.locator("#urls").fill("https://example.com/file.zip")
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#addVeil")).to_be_hidden()
        self.assertEqual(self.errors, [])

    def test_filters_and_link_grabber_work_without_engine(self):
        self.page.locator('[data-f="paused"]').click()
        expect(self.page.locator('[data-f="paused"]')).to_have_class("filter on", timeout=1500)
        self.page.locator("#lgBtn").click()
        expect(self.page.locator("#lgMetin")).to_be_visible(timeout=1500)
        self.assertEqual(self.page.locator("#lgMetin").input_value(), "")
        self.assertEqual(self.errors, [])

    def test_toolbar_and_sidebar_fit_small_window(self):
        for width, height in [(1180, 760), (914, 592), (704, 448)]:
            with self.subTest(width=width, height=height):
                self.page.set_viewport_size({"width": width, "height": height})
                for selector in ["#addBtn", "#lgBtn", "#pauseAll", "#resumeAll", "#search", "#clearDone", "#rulesOpen"]:
                    control = self.page.locator(selector)
                    control.scroll_into_view_if_needed()
                    box = control.bounding_box()
                    self.assertGreaterEqual(box["x"], 0)
                    self.assertLessEqual(box["x"] + box["width"], width + 1)
                    self.assertLessEqual(box["y"] + box["height"], height + 1)
                for selector in ["#addBtn", "#lgBtn", "#pauseAll", "#resumeAll"]:
                    lines = self.page.locator(selector).evaluate("""el => {
                        const range = document.createRange();
                        range.selectNodeContents(el);
                        return new Set([...range.getClientRects()].map(r => r.top)).size;
                    }""")
                    self.assertEqual(lines, 1, selector + " label wraps")


if __name__ == "__main__":
    unittest.main()
