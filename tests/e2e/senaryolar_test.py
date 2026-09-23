"""Kullanicinin masaustu akisini gercek API + headless UI ile suren E2E senaryolari."""
from __future__ import annotations

import hashlib
import ctypes
import json
import socket
import unittest
from unittest import mock
import urllib.error
import urllib.request
from pathlib import Path

from tests.e2e.kopru import GercekKopru, ROOT
from tests.fake_http import SunucuAyarlari, baslat


class Senaryolar(unittest.TestCase):
    def setUp(self):
        self.k = GercekKopru()
        self.k.manager.start()
        self.page = self.k.new_page()
        self.servers = []

    def tearDown(self):
        for server in self.servers:
            server.shutdown(); server.server_close()
        try:
            self.k.assert_clean(self)
            self.assertEqual([], self.k.console_errors, "console error")
        finally:
            self.k.close()

    def fake(self, data: bytes, delay=0, name="sample.bin"):
        settings = SunucuAyarlari(veri=data, gecikme_sn=delay)
        port, server = baslat(settings)
        server.handle_error = lambda request, address: None
        self.servers.append(server)
        return settings, f"http://127.0.0.1:{port}/{name}"

    def add(self, url):
        p = self.page
        p.locator("#addBtn").click()
        p.locator("#urls").fill(url)
        p.locator("#addGo").click()
        p.wait_for_function("url => state.items.some(item => item.source === url)", arg=url, timeout=15000)
        gid = p.evaluate("url => state.items.find(item => item.source === url).gid", arg=url)
        return p.locator(f'.row[data-gid="{gid}"]')

    def wait_complete(self, row, timeout=30000):
        self.page.wait_for_function("gid => { const r=document.querySelector(`.row[data-gid=\"${CSS.escape(gid)}\"]`); return r && r.classList.contains('complete'); }", arg=row.get_attribute("data-gid"), timeout=timeout)

    def test_S1_link_ekle_ilerleme_tamamlandi(self):
        data = (bytes(range(256)) * 2735)[:700_000]
        _, url = self.fake(data)
        row = self.add(url)
        self.assertIn("sample", row.inner_text())
        self.wait_complete(row)
        self.assertIn("Bitti", row.inner_text())
        self.assertIn("100.0%", row.inner_text())

    def test_S2_duraklat_devam_checksum(self):
        data = (bytes(range(251)) * 8000)[:2_000_000]
        _, url = self.fake(data, 1.5)
        row = self.add(url)
        self.page.wait_for_function("gid => document.querySelector(`.row[data-gid=\"${CSS.escape(gid)}\"]`)?.classList.contains('active')", arg=row.get_attribute("data-gid"), timeout=10000)
        row.locator('[data-act="pause"]').click()
        self.page.wait_for_function("gid => document.querySelector(`.row[data-gid=\"${CSS.escape(gid)}\"]`)?.classList.contains('paused')", arg=row.get_attribute("data-gid"))
        self.page.locator(f'.row[data-gid="{row.get_attribute("data-gid")}"] [data-act="resume"]').click()
        row = self.page.locator(f'.row[data-gid="{row.get_attribute("data-gid")}"]')
        self.wait_complete(row, 60000)
        item = self.k.manager.store.by_gid(row.get_attribute("data-gid"))
        target = Path(item["dest_dir"]) / item["filename"]
        self.assertEqual(hashlib.sha256(data).digest(), hashlib.sha256(target.read_bytes()).digest())

    def test_S3_klasor_ve_ac_varolan_yolu_aciyor(self):
        data = b"S3-file"
        _, url = self.fake(data)
        row = self.add(url); self.wait_complete(row)
        gid = row.get_attribute("data-gid")
        row.locator('[data-act="open"]').click()
        row = self.page.locator(f'.row[data-gid="{gid}"]')
        row.click(button="right")
        self.page.get_by_role("button", name="Dosyayı aç").click()
        self.assertTrue(self.k.os_calls)
        self.assertTrue(all(Path(path).exists() for _, path in self.k.os_calls))

    def test_S4_video_merger_ciktisi_dosya_adi_boyut_ac(self):
        title, content = "E2E Final Video", b"merged MP4 payload" * 4096
        output = self.k.root / "downloads" / f"{title}.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        self.k.fake_video = {"output": output, "content": content, "title": title}
        self.k.api.add_links({"urls": ["https://youtube.com/watch?v=e2e"], "dest_dir": str(output.parent)})
        gid = next(iter(self.k.manager.video_jobs))
        self.page.wait_for_function("gid => document.querySelector(`.row[data-gid=\"${CSS.escape(gid)}\"]`)", arg=gid)
        row = self.page.locator(f'.row[data-gid="{gid}"]')
        self.wait_complete(row)
        errors = []
        if title not in row.inner_text(): errors.append("satir basligi X degil")
        if f"{len(content)} B" not in row.inner_text(): errors.append(f"boyut satiri X.mp4 boyutu {len(content)} B degil: {row.inner_text()}")
        row.locator('[data-act="open"]').click()
        row.click(button="right")
        self.page.get_by_role("button", name="Dosyayı aç").click()
        if ("startfile", str(output)) not in self.k.os_calls: errors.append("Ac dugmesi X.mp4 yolunu acmadi")
        eski = self.k.root / "downloads" / "Eski.mp4"
        eski.write_bytes(b"fixed merged artifact")
        rid = self.k.manager.store.add("video", "https://youtube.com/watch?v=old", "Eski", str(eski.parent), {"title": "Eski"}, gid="yt:old-e2e")
        self.k.manager.store.update_by_id(rid, status="complete", filename="Eski.f10.m4a", total_bytes=137 * 1024 * 1024)
        self.k.manager.resolve_item_path("yt:old-e2e")
        old_row = self.k.manager.store.by_gid("yt:old-e2e")
        if old_row["filename"] != "Eski.mp4": errors.append("eski .f10.m4a dosya adi duzelmedi")
        if old_row["total_bytes"] != eski.stat().st_size: errors.append("eski kayit boyutu duzelmedi")
        self.assertEqual([], errors, "; ".join(errors))

    def test_S5_yetim_active_video_gizlenir(self):
        store = self.k.manager.store
        orphan_id = store.add("video", "https://different.invalid/v", "E2E Orphan", dest_dir=str(self.k.root / "downloads"), options={"title": "Ayni baslik"}, gid="yt:orphan-e2e")
        store.update_by_id(orphan_id, status="active")
        sibling_id = store.add("video", "https://other.invalid/v", "E2E kardes", dest_dir=str(self.k.root / "downloads"), options={"title": "Ayni baslik"}, gid="yt:sibling-e2e")
        store.update_by_id(sibling_id, status="complete")
        self.k.manager.stop(); self.k.api.paylasim_stop(); self.k.local.stop(); store.conn.close()
        from core.manager import Manager
        from api.server import LocalAPI
        self.k.manager = Manager()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
        self.k.local = LocalAPI(self.k.manager, port=port, lan=True); self.k.local.start()
        self.k.api = self.k.app.Api(self.k.manager, self.k.local); self.k.api.windows = None
        self.k.manager.start()
        self.page.reload(); self.page.evaluate("window.dispatchEvent(new Event('pywebviewready'))")
        self.assertFalse(self.page.locator('.row[data-gid="yt:orphan-e2e"]').count())

    def test_S6_agda_paylas_get_kapatma_silme_404(self):
        _, url = self.fake(b"share bytes")
        row = self.add(url); self.wait_complete(row)
        row.locator('[data-act="network-share"]').click()
        modal = self.page.locator("#shareVeil")
        self.assertTrue(modal.get_attribute("class").find("open") >= 0)
        link = self.page.locator("#shareLink").input_value()
        self.assertTrue(link.startswith("http://"))
        self.assertRegex(link, r"http://(?:127\.0\.0\.1|192\.168\.|10\.|172\.(?:1[6-9]|2\d|3[01])\.)")
        self.assertEqual(1, link.count("http://"))
        self.assertEqual(1, link.count("/s/"))
        self.assertTrue(self.page.locator("#shareQrImg").count() or self.page.locator("#shareQrBox canvas").count())
        with urllib.request.urlopen(link) as response: self.assertEqual(b"share bytes", response.read())
        self.page.locator('#shareVeil [data-close]').first.click()
        self.page.evaluate("openVeil('shareVeil')"); self.page.keyboard.press("Escape")
        self.assertNotIn("open", modal.get_attribute("class"))
        self.page.evaluate("openVeil('shareVeil')"); modal.click(position={"x": 4, "y": 4})
        self.assertNotIn("open", modal.get_attribute("class"))
        self.page.locator("#openShare").click()
        token = self.k.api.share_list()["shares"][0]["token"]
        self.page.evaluate("t => deleteShare(t)", token)
        self.page.wait_for_timeout(200)
        with self.assertRaises(urllib.error.HTTPError) as removed:
            urllib.request.urlopen(link)
        self.assertEqual(404, removed.exception.code)

    def test_S7_hover_satir_konumu_sabit(self):
        _, url = self.fake(b"hover")
        row = self.add(url); self.wait_complete(row)
        box1 = row.bounding_box(); row.hover(); self.page.wait_for_timeout(1000); box2 = row.bounding_box()
        for key in ("x", "y", "width", "height"):
            self.assertAlmostEqual(box1[key], box2[key], delta=1, msg=f"{key} oynadi")

    def test_S8_pencere_hesabi_ekrana_sigiyor(self):
        for width, height in ((1366, 768), (1920, 1080)):
            for dpi in (100, 150, 200):
                with mock.patch.object(self.k.app, "_calisma_alani", return_value=(0, 0, width, height, 1)):
                    with mock.patch.object(ctypes.windll.user32, "GetDpiForSystem", return_value=round(96 * dpi / 100)):
                        x, y, w, h, mw, mh = self.k.app.pencere_boyutu()
                self.assertGreaterEqual(x, 0); self.assertGreaterEqual(y, 0)
                self.assertLessEqual(x + w, width); self.assertLessEqual(y + h, height)
                self.assertLessEqual(mw, width); self.assertLessEqual(mh, height)
                self.page.set_viewport_size({"width": width, "height": height})
                self.page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth")
                self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth"))
                self.assertTrue(self.page.locator("#addBtn").is_visible())
                self.assertTrue(self.page.locator("#openFolder").is_visible())

    def test_S9_toplu_sil_kayit_ve_dosya(self):
        gids=[]
        paths=[]
        for n in (1, 2):
            _, url = self.fake(f"bulk{n}".encode(), name=f"bulk{n}.bin")
            row=self.add(url); self.wait_complete(row); gids.append(row.get_attribute("data-gid"))
            paths.append(Path(self.k.api.item_yolu(gids[-1])["yol"]))
        self.page.locator("#selectAllBtn").click(); self.page.locator("#removeSelected").click()
        self.page.locator("#remFiles").uncheck(); self.page.locator("#remGo").click()
        self.page.wait_for_timeout(500)
        for gid in gids: self.assertEqual("removed", self.k.manager.store.by_gid(gid)["status"])
        for path in paths: self.assertTrue(path.exists(), f"kayit sil dosyasi koru: {path}")
        for n in (3, 4):
            _, url = self.fake(f"bulk{n}".encode(), name=f"bulk{n}.bin")
            row = self.add(url); self.wait_complete(row); gids.append(row.get_attribute("data-gid"))
            paths.append(Path(self.k.api.item_yolu(gids[-1])["yol"]))
        self.page.locator("#selectAllBtn").click(); self.page.locator("#removeSelected").click()
        self.page.locator("#remFiles").check()
        self.assertTrue(self.page.locator("#remFiles").is_checked())
        self.page.locator("#remGo").click()
        self.page.wait_for_timeout(500)
        for gid in gids[2:]: self.assertEqual("removed", self.k.manager.store.by_gid(gid)["status"])
        js_calls = self.page.evaluate("window.__bridgeLog.filter(c => c[0] === 'control')")
        for gid, path in zip(gids[2:], paths[2:]):
            self.assertFalse(path.exists(), f"dosyayla sil: {path}; row={self.k.manager.store.by_gid(gid)}; calls={[c for c in self.k.api_calls if c[0] == 'control']}; js={js_calls}")

    def test_S10_paneller_ac_kapat_uncaught_hata_yok(self):
        for button, panel in (("#openSettings", "setVeil"), ("#openPlugins", "pluginVeil"),
                              ("#openServer", "srvVeil"), ("#openShare", "shareCenterVeil"),
                              ("#rulesOpen", "rulesVeil"), ("#lgBtn", "lgVeil")):
            self.page.locator(button).click()
            veil = self.page.locator("#" + panel)
            self.page.wait_for_function("id => document.querySelector('#'+id).classList.contains('open') || document.querySelector('#'+id).classList.contains('on')", arg=panel, timeout=7000)
            veil.locator("[data-close]").first.click()
            self.page.locator(button).click()
            self.page.keyboard.press("Escape")
            self.page.locator(button).click()
            veil.click(position={"x": 3, "y": 3})
        self.assertEqual([], self.k.pageerrors)

    def test_S11_TR_EN_anahtar_sizintisi_yok(self):
        self.page.locator("#openSettings").click()
        select=self.page.locator("#sLang")
        select.select_option("en"); self.page.wait_for_timeout(250)
        en=self.page.locator("body").inner_text()
        self.assertNotRegex(en, r"\b(?:share|row|add|state|bar)\.[A-Za-z0-9_.-]+")
        select.select_option("tr"); self.page.wait_for_timeout(250)
        tr=self.page.locator("body").inner_text()
        self.assertNotRegex(tr, r"\b(?:share|row|add|state|bar)\.[A-Za-z0-9_.-]+")


if __name__ == "__main__": unittest.main(verbosity=2)
