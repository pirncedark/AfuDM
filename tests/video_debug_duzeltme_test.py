"""Video taramasi regresyonlari; ag, motor ve guc islemleri taklit edilir."""
import io
import json
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import afuadm
import headless
from core import automation, dosya_adi, tracker_saglik as ts
from core.db import Store
from video import mp4mux as mux
from video.ytdlp import VideoJob


def fragment(offset=True, cts=None, version=0, base=None):
    flags = 0x020000 if base is None else 1
    tfhd = mux._kutu(b"tfhd", struct.pack(">II", flags, 1) +
                     (b"" if base is None else struct.pack(">Q", base)))
    truns = []
    for first in (True, False):
        flags = (1 if first and offset else 0) | (0x800 if cts is not None else 0)
        data = struct.pack(">II", (version << 24) | flags, 1)
        if flags & 1:
            data += struct.pack(">i", 100)
        if cts is not None:
            data += struct.pack(">i" if version else ">I", cts)
        truns.append(mux._kutu(b"trun", data))
    return mux._kutu(b"moof", mux._kutu(b"traf", tfhd, *truns))


class VideoDebugTests(unittest.TestCase):
    def test_01_merge_preserves_existing_alternative(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            video, audio = root / "a.f1.mp4", root / "a.f2.m4a"
            for path in (video, audio, root / "a.mp4", root / "a (birlesik).mp4"):
                path.write_bytes(b"old")
            job = VideoJob("yt:test", "https://example.com", folder,
                           parca_dosyalari=[str(video), str(audio)])
            def merge(v, a, target):
                Path(target).write_bytes(b"merged")
            with patch.object(mux, "izi_oku", side_effect=lambda p: SimpleNamespace(
                    tur="vide" if p == video else "soun")), patch.object(mux, "birlestir", side_effect=merge):
                job._kendi_birlestir()
            self.assertEqual((root / "a (birlesik).mp4").read_bytes(), b"old")
            self.assertEqual((root / job.filename).read_bytes(), b"merged")
            self.assertFalse(video.exists())

    def test_02_consecutive_truns_continue(self):
        for base, expected in ((None, [100, 104]), (50, [150, 154])):
            with self.subTest(base=base):
                data = fragment(base=base)
                samples = mux._parcali_ornekler(io.BytesIO(data), len(data), 1,
                                               {"sure": 1, "boyut": 4, "bayrak": 0})
                self.assertEqual([s.ofset for s in samples], expected)

    def test_03_pause_resume_send_request(self):
        for command in ("pause", "resume", "remove"):
            args = afuadm.komutlar_ayirici().parse_args([command, "123"])
            with patch.object(afuadm, "_istek", return_value={}) as request:
                self.assertEqual(afuadm.komut_kontrol(args), 0)
                self.assertEqual(request.call_args.args[2]["delete_files"], False)

    def test_04_move_rename_checksum_chain_survives_worker_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = Store(str(root / "jobs.sqlite"))
            try:
                source = root / "a.txt"
                source.write_bytes(b"abc")
                store.set("automation_steps", ["move", "rename", "checksum"])
                store.set("automation_move_to", str(root / "moved"))
                store.set("automation_rename_to", "renamed.txt")
                worker = automation.AutomationWorker(store, lambda _: None)
                worker.enqueue_download("test", {"dest_dir": folder, "filename": "a.txt",
                    "options": json.dumps({"checksum": "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"})})
                for _ in range(3):
                    worker = automation.AutomationWorker(store, lambda _: None)
                    worker._run(store.automation_claim())
                jobs = store.automation_jobs("test")
                self.assertEqual([j["status"] for j in jobs], ["complete"] * 3)
                self.assertEqual((root / "moved" / "renamed.txt").read_bytes(), b"abc")
            finally:
                store.conn.close()

    def test_05_headless_startup_always_releases_resources(self):
        for stage in ("constructor", "start", "service", "access", "server", "cleanup"):
            with self.subTest(stage=stage):
                lock, manager, service, api = Mock(), Mock(), Mock(), Mock()
                lock.al.return_value = (True, {})
                manager.store.get.return_value = False
                service.erisim.yonetici_var_mi.return_value = True
                service.sunucu_baslat.return_value = {"ok": False}
                if stage == "start": manager.start.side_effect = RuntimeError("start")
                if stage == "access": service.erisim.yonetici_var_mi.side_effect = RuntimeError("access")
                if stage == "server": service.sunucu_baslat.side_effect = RuntimeError("server")
                if stage == "cleanup": service.sunucu_durdur.side_effect = RuntimeError("cleanup")
                with patch.object(headless.paths, "ensure_dirs"), patch.object(headless.paths, "ARIA2C", SimpleNamespace(exists=lambda: True)), \
                     patch.object(headless.ornek, "OrnekKilidi", return_value=lock), \
                     patch.object(headless, "Manager", side_effect=RuntimeError("constructor") if stage == "constructor" else lambda: manager), \
                     patch.object(headless, "AfuDMServis", side_effect=RuntimeError("service") if stage == "service" else lambda *a, **k: service), \
                     patch.object(headless, "LocalAPI", return_value=api), redirect_stdout(io.StringIO()):
                    try: headless.calistir()
                    except RuntimeError: pass
                lock.birak.assert_called_once()
                if stage != "constructor": manager.stop.assert_called_once()
                if stage in ("access", "server", "cleanup"): api.stop.assert_called_once()

    def test_06_invalid_udp_port_does_not_abort_scan(self):
        addresses = ["udp://example.com:bad/announce", "udp://example.com:99999/announce",
                     "udp://example.com:0/announce"]
        with patch.object(ts.socket, "socket", side_effect=AssertionError("network forbidden")):
            result = ts.tara(addresses)
        self.assertEqual(result["olu"], addresses)

    def test_07_scrape_reads_exact_hash_and_keys(self):
        data = (b"d5:filesd20:xxxxxxxxxxxxxxxxxxxxd8:completei99e10:incompletei88ee"
                b"20:abcdefghijklmnopqrstd10:incompletei7e8:completei2eeee")
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = data
        with patch.object(ts.urllib.request, "urlopen", return_value=response):
            self.assertEqual(ts._http_scrape("https://example.com/announce", b"abcdefghijklmnopqrst".hex()),
                             ("canli", 2, 7))

    def test_08_negative_cts_uses_signed_version(self):
        table = mux._ctts([mux.Ornek(0, 4, 1, -1)])
        self.assertEqual(table[8], 1)
        self.assertEqual(struct.unpack_from(">i", table, 20)[0], -1)

    def test_08_unsigned_cts_is_not_negative(self):
        data = fragment(cts=0xffffffff)
        samples = mux._parcali_ornekler(io.BytesIO(data), len(data), 1,
                                       {"sure": 1, "boyut": 4, "bayrak": 0})
        self.assertEqual(samples[0].cts, 4294967295)
        table = mux._ctts(samples)
        self.assertEqual(table[8], 0)

    def test_09_device_names_with_multiple_dots(self):
        for name in ("CON.foo.txt", "COM1.tar.gz", "NUL.001"):
            self.assertEqual(dosya_adi.guvenli_dosya_adi(name), "_" + name)

    def test_10_failed_sleep_is_recorded_as_error(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(str(Path(folder) / "jobs.sqlite"))
            try:
                store.set("automation_power", "sleep")
                store.set("automation_power_seconds", 5)
                store.automation_enqueue("test", "power", {})
                worker = automation.AutomationWorker(store, lambda _: None)
                original = store.automation_update
                def update(job_id, **fields):
                    original(job_id, **fields)
                    if "status" in fields: worker.stop_event.set()
                with patch.object(store, "automation_update", side_effect=update), \
                     patch.object(automation.time, "sleep"), patch.object(automation.guc, "uyut", return_value=False):
                    worker._loop()
                self.assertEqual(store.automation_jobs("test")[0]["status"], "error")
            finally: store.conn.close()

    def test_11_raw_error_is_logged_not_shown(self):
        """`error` ham metni korur (eski sozlesme); `errorMessage` tek cumle verir."""
        raw = "ERROR: HTTP Error 403: Forbidden"
        for expected, ham in (
            ("yeniden", raw),
            ("gizli", "ERROR: [youtube] abc: Private video. Sign in if you've been granted access"),
            ("oturum", "ERROR: [youtube] abc: Sign in to confirm you're not a bot"),
            ("bolgede", "ERROR: [youtube] abc: The uploader has not made this video available in your country"),
            ("kaldirilmis", "ERROR: [youtube] abc: This video has been removed by the uploader"),
            ("bulunamadi", "ERROR: [youtube] abc: Video unavailable. This video is private or deleted"),
            ("Cok fazla", "ERROR: HTTP Error 429: Too Many Requests"),
        ):
            with self.subTest(ham=ham):
                job = VideoJob("yt:test", "https://example.com", ".", dil="tr")
                with self.assertLogs("video.ytdlp", level="WARNING") as logs:
                    job.ham_hata = ham
                    job.error = job.anlasilir_hata(ham)
                    self.assertEqual(job.error, ham)              # eski sozlesme
                    self.assertTrue(any(ham in entry for entry in logs.output))
                    message = job.to_dict()["errorMessage"]      # kullaniciya giden
                self.assertNotIn("403", message)
                self.assertNotIn("ERROR", message)
                self.assertIn(expected, message)

    def test_11_user_message_follows_language(self):
        for dil, expected in (("tr", "Baglantiyi"), ("en", "connection")):
            with self.subTest(dil=dil):
                job = VideoJob("yt:test", "https://example.com", ".", dil=dil)
                job.ham_hata = "ERROR: HTTP Error 500: Internal Server Error"
                job.error = job.anlasilir_hata(job.ham_hata)
                self.assertIn(expected, job.to_dict()["errorMessage"])

    def test_11_note_and_merge_errors_pass_through(self):
        job = VideoJob("yt:test", "https://example.com", ".", dil="tr")
        job.error = "Video birlestirilemedi; yeniden indirmeyi deneyin."
        self.assertEqual(job.to_dict()["errorMessage"], job.error)

    def test_12_speed_units_are_bytes_based(self):
        for value, expected in ((0, "0.0 B"), (1024, "1.0 KB"), (1048576, "1.0 MB")):
            self.assertEqual(afuadm.human_size(value), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
