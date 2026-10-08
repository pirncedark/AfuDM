"""The prompt's primary action fits its fixed client area in both languages."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel=os.environ.get('AFUDM_TEST_BROWSER', 'msedge'), headless=True)
    try:
        page = browser.new_page(viewport={'width': 520, 'height': 481})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto((ROOT / 'ui/download.html').as_uri())
        for language in ('tr', 'en'):
            page.evaluate('''(language) => {
                lang.setLang(language); lang.applyStatic();
                document.getElementById('url').textContent = 'https://example.test/pdf?' + 'x'.repeat(3000);
                document.getElementById('qualityWrap').hidden = false;
                document.getElementById('error').textContent = lang.t('download.folderError');
            }''', language)
            button = page.locator('#start').bounding_box()
            assert button and button['y'] >= 0 and button['y'] + button['height'] <= 481, (language, button)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        print('Download prompt layout: TR/EN video action fits 520x481 client area')
        page.evaluate('''async () => {
            window.setInterval = () => 0;
            window.pywebview = {api: {
                pencere_durumu: async () => ({reset:0}), dil: async () => 'tr', baslik: async () => ({}),
                bekleyen_listesi: async () => ({ogeler:[{id:1,source:'browser',url:'https://example.test/a.pdf',kind:'http',filename:'a.pdf'}]}),
                bekleyen_goster: async () => ({ok:true}),
                kaydet_bilgi: async () => ({ana:'/downloads',son_klasor:'/remembered'}),
                klasor_gozat: async () => ({ok:false}),
                bekleyen_onayla: async (id, options) => {window.chosen = options; return {ok:false,error_code:'folder'};}
            }};
            await window.afudmDownloadRefresh();
        }''')
        assert page.locator('#folder').input_value() == '/remembered'
        page.locator('#browse').click()
        page.wait_for_function("document.getElementById('error').textContent === lang.t('download.browseFailed')")
        page.evaluate("window.pywebview.api.klasor_gozat = async () => ({ok:true,yol:'/chosen'})")
        page.locator('#browse').click()
        page.wait_for_function("document.getElementById('folder').value === '/chosen'")
        page.locator('#resetFolder').click()
        assert page.locator('#folder').input_value() == '/downloads'
        page.locator('#folder').fill('/manual')
        page.locator('#name').fill('manual.pdf')
        page.locator('#start').click()
        page.wait_for_function("window.chosen?.dest_dir === '/manual'")
        assert page.evaluate('window.chosen.filename') == 'manual.pdf'
        page.wait_for_function("document.getElementById('error').textContent === lang.t('download.folderError')")
        print('Download prompt Playwright: remembered folder, browse failure/success, reset, manual name/path and folder error passed')
    finally:
        browser.close()
