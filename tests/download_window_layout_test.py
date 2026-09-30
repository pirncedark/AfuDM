"""The prompt's primary action fits its fixed client area in both languages."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel=os.environ.get('AFUDM_TEST_BROWSER', 'msedge'), headless=True)
    try:
        page = browser.new_page(viewport={'width': 520, 'height': 421})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto((ROOT / 'ui/download.html').as_uri())
        for language in ('tr', 'en'):
            page.evaluate('''(language) => {
                lang.setLang(language); lang.applyStatic();
                document.getElementById('url').textContent = 'https://example.test/pdf?' + 'x'.repeat(3000);
                document.getElementById('qualityWrap').hidden = false;
            }''', language)
            button = page.locator('#start').bounding_box()
            assert button and button['y'] >= 0 and button['y'] + button['height'] <= 421, (language, button)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        print('Download prompt layout: TR/EN video action fits 520x421 client area')
    finally:
        browser.close()
