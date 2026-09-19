# -*- coding: utf-8 -*-
"""CLI + yeni v1.3.2 yetenekleri: hiz profili (mode), link yenileme (renew),
zamanlama cozumleme. Hicbiri ag kullanmaz: uydurma RPC ile calisir.

Senaryo: FDM'nin "Snail Mode"u ve NDM'nin "Renew expired link"i. aria2'ye
canli ve JSON-RPC uzerinden, inilen baytlari koruyarak is verilir.

Sozlesme (v1.3.2 gri yuzeyi): renew yalnizca http(s)/ftp; torrent/magnet/video
RENEW_UNSUPPORTED ile reddedilir; kontrol (pause/resume/remove) kaydi yoksa
KAYIT_YOK ile istemciye makine-okur kod doner (CLI exit 3).
"""
import sys
import tempfile
import threading
import time

sys.path.insert(0, r"C:\Users\afuuu\AfuDM")

from core.db import Store  # noqa: E402
from core.hata import AfuHata, KayitYok, RenewDesteklenmez  # noqa: E402
from core.manager import HIZ_PROFILLERI, Manager  # noqa: E402

fails: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("  [GECTI] " if condition else "  [BASARISIZ] ") + name + (f" — {detail}" if detail else ""))
    if not condition:
        fails.append(name)


class SahteRpc:
    """manager.rpc yerine gecen kayitci. changeUri neyin ulandiigini dogrular."""

    def __init__(self) -> None:
        self.cagri: list[tuple] = []
        self.durum = "active"      # senaryo icin degistirilebilir

    def change_global_option(self, options: dict) -> str:
        self.cagri.append(("change_global_option", options))
        return "OK"

    def tell_status(self, gid, keys) -> dict:
        return {
            "status": self.durum,
            "files": [{"uris": [{"uri": "http://eski.adres.com/dosya.zip", "status": "used"}]}],
        }

    def pause(self, gid) -> str:
        self.cagri.append(("pause", gid))
        return "OK"

    def unpause(self, gid) -> str:
        self.cagri.append(("unpause", gid))
        return "OK"

    def change_uri(self, gid, file_index, del_uris, add_uris, position=-1) -> int:
        self.cagri.append(("change_uri", gid, file_index, del_uris, add_uris, position))
        return len(del_uris) + len(add_uris)

    def change_option(self, gid, options: dict) -> str:
        self.cagri.append(("change_option", gid, options))
        return "OK"


def kurulum() -> tuple[Manager, SahteRpc, Store]:
    """BOS uzerine secili manager: gercek daemon/acilim YOK."""
    tmp = tempfile.mkdtemp(prefix="afudm_cli_")
    depo = Store(tmp + r"\x.db")
    m = Manager.__new__(Manager)
    m.store = depo
    m.rpc = SahteRpc()
    m.last_error = ""
    m.video_jobs = {}
    m._cerezler = {}
    m._lock = threading.RLock()
    return m, m.rpc, depo


m, rpc, depo = kurulum()

print("1) Hiz profili (mode)")
check("varsayilan normal", depo.get("hiz_profili") == "normal")
check("salyangoz limiti varsayilan 100 KB/s", depo.get("snail_speed_kb") == 100)
check("uc profil tanimli", set(HIZ_PROFILLERI) == {"snail", "normal", "turbo"})

# degisik ayarlar: kullanici hiz siniri 500 KB/s
depo.set("max_speed_kb", 500)
check("normal = kullanici limiti", m.hiz_limiti_kb() == 500)
depo.set("hiz_profili", "snail")
check("salyangoz = 100 KB/s", m.hiz_limiti_kb() == 100)
depo.set("hiz_profili", "turbo")
check("turbo = sinirsiz (0)", m.hiz_limiti_kb() == 0)

try:
    m.set_mode("gunluk")
    check("gecersiz profil RED", False, "ValueError bekleniyordu")
except ValueError:
    check("gecersiz profil RED", True)

sonuc = m.set_mode("snail")
go_kaydi = next(x for x in rpc.cagri if x[0] == "change_global_option")
check("snail CANLI uygulanir (100K)", go_kaydi[1].get("max-overall-download-limit") == "100K", str(go_kaydi))
check("profilleri ayarlandi", sonuc["profil"] == "snail" and sonuc["limit_kb"] == 100)
check("profil DB'ye yazildi", m.store.get("hiz_profili") == "snail")

rpc2_sonuc = m.set_mode("turbo")
go2 = [x for x in rpc.cagri if x[0] == "change_global_option"][-1]
check("turbo CANLI uygulanir (0 = sinirsiz)", go2[1].get("max-overall-download-limit") == "0", str(go2))

# turbo -> normal: kullanicinin en son kayitli siniri GERI GELIR (normal tek
# kaynak: max_speed_kb; turbo'nun "sinirsiz" olgusu normal profile tasmaz).
depo.set("hiz_profili", "turbo")
depo.set("max_speed_kb", 500)
m.set_mode("normal")
check("turbo->normal eski limiti korur", m.hiz_limiti_kb() == 500, str(m.hiz_limiti_kb()))
go3 = [x for x in rpc.cagri if x[0] == "change_global_option"][-1]
check("normal CANLI 500K uygulanir", go3[1].get("max-overall-download-limit") == "500K", str(go3))

print("2) Link yenileme (renew)")
kimlik = depo.add(kind="http", source="http://eski.adres.com/dosya.zip",
                  title="Deneme", dest_dir="C:/test", options={}, gid="abc123")
try:
    m.renew("yok", "https://yeni.com/f.zip")
    check("olmayan gid RED", False)
except KayitYok as e:
    check("olmayan gid RED (KAYIT_YOK)", e.code == "KAYIT_YOK")
try:
    m.renew("abc123", "duz-metin-adres")
    check("gecersiz yeni adres RED", False)
except AfuHata as e:
    check("gecersiz yeni adres RED (BAD_SOURCE)", e.code == "BAD_SOURCE")

# Renomre yok: torrent/magnet/video islemleri changeUri istemez -> RENEW_UNSUPPORTED
depo.add(kind="torrent", source="magnet:?xt=urn:btih:abc", title="Tor",
         dest_dir="C:/test", options={}, gid="torr1")
try:
    m.renew("torr1", "https://yeni.com/f.zip")
    check("torrent renew RED", False)
except RenewDesteklenmez as e:
    check("torrent renew RED (RENEW_UNSUPPORTED)", e.code == "RENEW_UNSUPPORTED")
depo.add(kind="video", source="https://youtube.com/watch?v=x", title="Vid",
         dest_dir="C:/test", options={}, gid="yt:1")
try:
    m.renew("yt:1", "https://yeni.com/f.zip")
    check("video renew RED", False)
except RenewDesteklenmez as e:
    check("video renew RED (RENEW_UNSUPPORTED)", e.code == "RENEW_UNSUPPORTED")

cagri_sayisi = len(rpc.cagri)
r = m.renew("abc123", "https://yeni.adres.com/dosya.zip")
cu = [x for x in rpc.cagri if x[0] == "change_uri"]
check("changeUri eski->yeni", bool(cu) and cu[0][3] == ["http://eski.adres.com/dosya.zip"]
      and cu[0][4] == ["https://yeni.adres.com/dosya.zip"], str(cu))
check("aktifse once duraklatildi", ("pause", "abc123") in rpc.cagri)
check("aktifse sonra devam", ("unpause", "abc123") in rpc.cagri)
check("degisen URI raporlanir", r["degisen"] == 2, str(r))
sira = [x[0] for x in rpc.cagri if x[0] in ("pause", "change_uri", "unpause")]
check("sira dogru (pause->changeUri->unpause)", sira == ["pause", "change_uri", "unpause"], str(sira))
row = depo.by_gid("abc123")
check("DB kaynagi yeni adres", row and row["source"] == "https://yeni.adres.com/dosya.zip")
check("DB durum aktif", row and row["status"] == "active")

# error'daki is de duraklatilmadan yenilenir (zaten akmiyor)
rpc.durum = "error"
m.renew("abc123", "https://ucuncu.adres.com/dosya.zip")
sira2 = [x[0] for x in rpc.cagri if x[0] in ("pause", "change_uri", "unpause")]
check("error'da pause atlanir", sira2[-3:] != ["pause", "change_uri", "unpause"], str(sira2[-3:]))
check("error'da devam ettirilir", sira2[-1] == "unpause", str(sira2[-1:]))

# Genisletilmis renew: headers/cookies/user_agent ayni atomik adimda changeOption
# ve DB'ye islenir (gelecekteki CLI'lar imzayi genisletmeden ilerleyebilir)
rpc.durum = "active"
depo.add(kind="http", source="http://eski2.adres.com/a.zip", title="Iki",
         dest_dir="C:/test", options={}, gid="abc9")
r2 = m.renew(
    "abc9",
    "https://yeni2.adres.com/a.zip",
    headers={"Authorization": "Bearer xyz", "X-Ek": "1"},
    cookies=[{"name": "sid", "value": "abc", "domain": "yeni2.adres.com"}],
    user_agent="AfuDM-Test/1.0",
)
co = [x for x in rpc.cagri if x[0] == "change_option"]
check("renew change_option cagirdi", bool(co), str(co))
check("basliklar seceneklere yazilir", co and "Authorization: Bearer xyz" in co[0][2]["header"], str(co))
check("cookie satiri var", co and any(l.startswith("Cookie: ") for l in co[0][2]["header"]), str(co))
check("user-agent secenegi var", co and co[0][2]["user-agent"] == "AfuDM-Test/1.0", str(co))
row2 = depo.by_gid("abc9")
opt2 = __import__("json").loads(row2["options"] or "{}")
check("DB basliklar islendi", opt2.get("headers", {}).get("Authorization") == "Bearer xyz", str(opt2))
check("DB user_agent islendi", opt2.get("user_agent") == "AfuDM-Test/1.0", str(opt2))
check("DB kaynagi yeni adres (iki)", row2["source"] == "https://yeni2.adres.com/a.zip")

print("2b) Kontrol kayitlari (exit kodu 3 sozlesmesi: KAYIT_YOK)")
for islem in (m.pause, m.resume):
    try:
        islem("bilinmeyen-gid")
        check("%s bilinmeyen gid RED" % islem.__name__, False)
    except KayitYok as e:
        check("%s bilinmeyen gid RED (KAYIT_YOK)" % islem.__name__, e.code == "KAYIT_YOK")
try:
    m.remove("bilinmeyen-gid")
    check("remove bilinmeyen gid RED", False)
except KayitYok:
    check("remove bilinmeyen gid RED (KAYIT_YOK)", True)

print("3) Zamanlama cozumleme (_zamanla) — YEREL SAAT, gecmisse yarina")
from api.server import _zamanla  # noqa: E402
simdi = time.time()
t = _zamanla("00:00")
check("saat:dakika epoch doner", isinstance(t, float) and abs(t - simdi) < 2 * 86400, str(t))
check("tam tarih kabul", isinstance(_zamanla("2026-12-31 23:59"), float))
try:
    _zamanla("carpik")
    check("bozuk zamanlama RED", False)
except ValueError:
    check("bozuk zamanlama RED", True)


def _yerel_beklenti(h: int, m: int) -> float:
    """_zamanla'nin karariyla BIREBIR: yerel saatte mktime(localtime) — gecerse
    +1 gun. (DST duyarsiz akis; Windows yerel saat dilimine baglidır.)"""
    suan = time.localtime()
    cal = time.struct_time((
        suan.tm_year, suan.tm_mon, suan.tm_mday, h, m, 0, -1, -1, -1))
    hedef = time.mktime(cal)
    return hedef + (86400.0 if hedef <= time.time() else 0.0)


check("00:00 gecmis -> yarin 00:00 (yerel)",
      abs(_zamanla("00:00") - _yerel_beklenti(0, 0)) < 1.0,
      str(_zamanla("00:00")))
check("gelecek HH:MM yerel zamanla hesaplanir",
      abs(_zamanla("23:58") - _yerel_beklenti(23, 58)) < 1.0,
      str(_zamanla("23:58")))
suan = time.localtime()
gelecek_h = (suan.tm_hour + 2) % 24
gelecek_m = suan.tm_min
check("gelecek ile karsilastirilabilir HH:MM (yerel)",
      abs(_zamanla("%02d:%02d" % (gelecek_h, gelecek_m))
          - _yerel_beklenti(gelecek_h, gelecek_m)) < 1.0,
      str(_zamanla("%02d:%02d" % (gelecek_h, gelecek_m))))
tarih = _zamanla("2030-01-01 12:00")
check("tam tarih gun kaymaz", abs(tarih - time.mktime(time.strptime("2030-01-01 12:00", "%Y-%m-%d %H:%M"))) < 1.0,
      str(tarih))

print()
if fails:
    print("BASARISIZ:", ", ".join(fails))
    sys.exit(1)
print("Hepsi gecti")