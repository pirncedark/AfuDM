# -*- coding: utf-8 -*-
"""Rol tabanli erisim denetimi — v2.1 Headless Server.

Tasarim kararlari (ve SINIRLARI):

* Anahtarin KENDISI hicbir yerde saklanmaz. Veritabaninda yalnizca SHA-256
  ozeti ve insanin taniyabilmesi icin ilk 6 karakterlik "onek" durur.
  Anahtar SADECE uretildigi anda bir kez donulur; kaybedilirse ROTASYON ile
  yenisi alinir.
* Rotasyon ayni satirin ozetini degistirir: eski anahtar ANINDA gecersizdir
  (bir sonraki istekte dogrulama basarisiz olur). Gecis suresi YOKTUR.
* Anahtar, parola, cerez ve sorgu parametreleri ASLA loglanmaz. Olay
  kaydina yalnizca anahtarin ADI, ROLU ve ONEKI yazilir.
* Hiz sinirlama BELLEKTE tutulur (surec omru). Bu bir DDoS korumasi DEGILDIR;
  kaba kuvvet denemesini ve kazara istek yagmurunu yavaslatir. Surec yeniden
  baslarsa sayaclar sifirlanir — yanlis bir guvenlik iddiasi kurmamak icin
  bu acikca boyle belirtilmistir.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time

# --- roller ---------------------------------------------------------------
ROL_YONETICI = "yonetici"
ROL_SALT_OKUR = "salt_okur"
ROLLER = (ROL_YONETICI, ROL_SALT_OKUR)

# Rolun yapabildikleri. "yaz" = durum degistiren her sey.
IZINLER: dict[str, set[str]] = {
    ROL_YONETICI: {"oku", "yaz", "ayar", "yonet"},
    ROL_SALT_OKUR: {"oku"},
}

ONEK_UZUNLUK = 6
ANAHTAR_ONEKI = "afudm_"


def rol_gecerli(rol: str) -> str:
    rol = (rol or "").strip().lower()
    if rol not in ROLLER:
        raise ValueError("rol 'yonetici' veya 'salt_okur' olmali")
    return rol


def izinli(rol: str, izin: str) -> bool:
    return izin in IZINLER.get(rol, set())


def _ozet(gizli: str) -> str:
    return hashlib.sha256(gizli.encode("utf-8")).hexdigest()


def _yeni_gizli() -> str:
    return ANAHTAR_ONEKI + secrets.token_urlsafe(32)


class HizSinirlayici:
    """IP basina istek penceresi + hatali dogrulama kilidi.

    Iki ayri mekanizma:
      1) Kayan pencere: son 60 saniyede `limit` istekten fazlasi 429.
      2) Kaba kuvvet kilidi: ust uste `hatali_limit` yanlis anahtar -> IP
         `kilit_saniye` boyunca 429. Dogru anahtar sayaci sifirlar.
    BELLEKTE tutulur; surec yeniden baslayinca sifirlanir (bkz. modul basligi).
    """

    PENCERE = 60.0

    def __init__(self, limit: int = 120, hatali_limit: int = 8,
                 kilit_saniye: int = 300) -> None:
        self._lock = threading.Lock()
        self.limit = max(1, int(limit))
        self.hatali_limit = max(1, int(hatali_limit))
        self.kilit_saniye = max(5, int(kilit_saniye))
        self._istekler: dict[str, list[float]] = {}
        self._hatalar: dict[str, int] = {}
        self._kilitler: dict[str, float] = {}

    def ayarla(self, limit: int | None = None, hatali_limit: int | None = None,
               kilit_saniye: int | None = None) -> None:
        """Canli ayar: yeni degerler HEMEN gecerlidir, yeniden baslatma yok."""
        with self._lock:
            if limit is not None:
                self.limit = max(1, int(limit))
            if hatali_limit is not None:
                self.hatali_limit = max(1, int(hatali_limit))
            if kilit_saniye is not None:
                self.kilit_saniye = max(5, int(kilit_saniye))

    def kilitli_mi(self, ip: str) -> float:
        """Kilitliyse KALAN saniye, degilse 0."""
        with self._lock:
            bitis = self._kilitler.get(ip, 0.0)
            kalan = bitis - time.time()
            if kalan <= 0:
                self._kilitler.pop(ip, None)
                return 0.0
            return kalan

    def izin_ver(self, ip: str) -> tuple[bool, float]:
        """(izin, kalan_saniye). izin False ise 429 donulmelidir."""
        kalan = self.kilitli_mi(ip)
        if kalan:
            return False, kalan
        simdi = time.time()
        with self._lock:
            kayit = [t for t in self._istekler.get(ip, []) if simdi - t < self.PENCERE]
            if len(kayit) >= self.limit:
                kayit.append(simdi)
                self._istekler[ip] = kayit[-self.limit * 2:]
                return False, max(0.0, self.PENCERE - (simdi - kayit[0]))
            kayit.append(simdi)
            self._istekler[ip] = kayit
            return True, 0.0

    def hatali(self, ip: str) -> None:
        with self._lock:
            sayi = self._hatalar.get(ip, 0) + 1
            self._hatalar[ip] = sayi
            if sayi >= self.hatali_limit:
                self._kilitler[ip] = time.time() + self.kilit_saniye
                self._hatalar[ip] = 0

    def basarili(self, ip: str) -> None:
        with self._lock:
            self._hatalar.pop(ip, None)

    def durum(self) -> dict:
        with self._lock:
            simdi = time.time()
            return {
                "limit": self.limit,
                "pencere_sn": int(self.PENCERE),
                "hatali_limit": self.hatali_limit,
                "kilit_saniye": self.kilit_saniye,
                "izlenen_ip": len(self._istekler),
                "kilitli_ip": sum(1 for b in self._kilitler.values() if b > simdi),
                "kalici": False,  # surec omru — yanlis guvenlik iddiasi yok
            }

    def kilitleri_temizle(self) -> int:
        with self._lock:
            sayi = len(self._kilitler)
            self._kilitler.clear()
            self._hatalar.clear()
            return sayi


class ErisimDeposu:
    """api_keys / api_clients / server_profiles tablolarinin tek kapisi."""

    def __init__(self, store) -> None:
        self.store = store
        self._lock = store._lock

    @property
    def _conn(self):
        # Restore can replace the underlying connection while preserving the
        # shared Store object. Resolve it at use time rather than caching it.
        return self.store.conn

    # --- anahtarlar -------------------------------------------------------
    def anahtar_olustur(self, ad: str, rol: str, not_metni: str = "") -> dict:
        """Yeni anahtar. Gizli deger SADECE BURADA, BIR KEZ donulur."""
        ad = (ad or "").strip()[:64]
        if not ad:
            raise ValueError("anahtar adi gerekli")
        rol = rol_gecerli(rol)
        gizli = _yeni_gizli()
        simdi = time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO api_keys(ad, rol, gizli_hash, onek, olusturuldu, not_metni)"
                " VALUES(?,?,?,?,?,?)",
                (ad, rol, _ozet(gizli), gizli[len(ANAHTAR_ONEKI):][:ONEK_UZUNLUK],
                 simdi, (not_metni or "")[:200]),
            )
            self._conn.commit()
            kimlik = int(cur.lastrowid)
        self.store.log("info", "erisim anahtari olusturuldu: %s (%s)" % (ad, rol))
        return {"id": kimlik, "ad": ad, "rol": rol, "gizli": gizli,
                "olusturuldu": simdi}

    def anahtar_rotasyon(self, key_id: int) -> dict:
        """Anahtari yenile. ESKISI ANINDA GECERSIZ olur (ayni satir, yeni ozet).

        Ayrica o anahtarla acilmis TUM istemci oturumlari kapatilir: eski
        anahtarla acilmis bir panel sekmesi devam edemez.
        """
        kayit = self.anahtar(key_id)
        if kayit is None:
            raise ValueError("anahtar bulunamadi")
        if kayit["iptal"]:
            raise ValueError("iptal edilmis anahtar yenilenemez")
        gizli = _yeni_gizli()
        simdi = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE api_keys SET gizli_hash = ?, onek = ?, son_rotasyon = ?"
                " WHERE id = ?",
                (_ozet(gizli), gizli[len(ANAHTAR_ONEKI):][:ONEK_UZUNLUK], simdi, key_id),
            )
            self._conn.execute(
                "UPDATE api_clients SET iptal = 1 WHERE key_id = ?", (key_id,))
            self._conn.commit()
        self.store.log("info", "erisim anahtari yenilendi: %s" % kayit["ad"])
        return {"id": key_id, "ad": kayit["ad"], "rol": kayit["rol"],
                "gizli": gizli, "son_rotasyon": simdi}

    def anahtar_iptal(self, key_id: int) -> dict:
        kayit = self.anahtar(key_id)
        if kayit is None:
            raise ValueError("anahtar bulunamadi")
        with self._lock:
            self._conn.execute("UPDATE api_keys SET iptal = 1 WHERE id = ?", (key_id,))
            self._conn.execute(
                "UPDATE api_clients SET iptal = 1 WHERE key_id = ?", (key_id,))
            self._conn.commit()
        self.store.log("info", "erisim anahtari iptal edildi: %s" % kayit["ad"])
        return {"id": key_id, "iptal": True}

    def anahtar_sil(self, key_id: int) -> dict:
        """Iptal edilmis bir anahtarin kaydini tamamen kaldirir (idempotent)."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM api_keys WHERE id = ? AND iptal = 1", (int(key_id),))
            self._conn.execute(
                "DELETE FROM api_clients WHERE key_id = ?", (int(key_id),))
            self._conn.commit()
        return {"id": int(key_id), "silindi": True}

    def anahtar_rol_ayarla(self, key_id: int, rol: str) -> dict:
        rol = rol_gecerli(rol)
        if self.anahtar(key_id) is None:
            raise ValueError("anahtar bulunamadi")
        with self._lock:
            self._conn.execute("UPDATE api_keys SET rol = ? WHERE id = ?", (rol, key_id))
            self._conn.execute(
                "UPDATE api_clients SET rol = ? WHERE key_id = ?", (rol, key_id))
            self._conn.commit()
        return {"id": key_id, "rol": rol}

    def anahtar(self, key_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM api_keys WHERE id = ?", (int(key_id),)).fetchone()
        return self._anahtar_disa(row) if row else None

    def anahtarlar(self) -> list[dict]:
        """Listeleme. `gizli_hash` DISARI CIKMAZ."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM api_keys ORDER BY iptal ASC, olusturuldu DESC").fetchall()
        return [self._anahtar_disa(r) for r in rows]

    @staticmethod
    def _anahtar_disa(row) -> dict:
        return {
            "id": int(row["id"]),
            "ad": row["ad"],
            "rol": row["rol"],
            "onek": row["onek"],
            "olusturuldu": row["olusturuldu"],
            "son_kullanim": row["son_kullanim"],
            "son_rotasyon": row["son_rotasyon"],
            "iptal": bool(row["iptal"]),
            "not_metni": row["not_metni"] or "",
        }

    def dogrula(self, sunulan: str) -> dict | None:
        """Anahtari dogrula. Gecerliyse anahtar kaydi, degilse None.

        Karsilastirma SABIT ZAMANLIDIR (hmac.compare_digest) ve yalnizca
        ozetler uzerinden yapilir."""
        if not sunulan or not isinstance(sunulan, str):
            return None
        ozet = _ozet(sunulan)
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM api_keys WHERE iptal = 0").fetchall()
        for row in rows:
            if hmac.compare_digest(str(row["gizli_hash"]), ozet):
                return self._anahtar_disa(row)
        return None

    def kullanim_isle(self, key_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE api_keys SET son_kullanim = ? WHERE id = ?",
                (time.time(), int(key_id)))
            self._conn.commit()

    def yonetici_var_mi(self) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM api_keys WHERE iptal = 0 AND rol = ?",
                (ROL_YONETICI,)).fetchone()
        return row is not None

    # --- istemciler -------------------------------------------------------
    def oturum_ac(self, key_id: int, rol: str, ip: str, istemci: str) -> str:
        """Bir anahtarla baglanan istemci icin oturum kimligi uretir.

        Oturum kimligi tarayiciya donulur ve sonraki isteklerde
        `X-AfuDM-Oturum` basligiyla gelir. Anahtarin yerine GECMEZ: her istek
        yine anahtarla dogrulanir; oturum yalnizca "kim bagli" ekrani ve tekil
        iptal icindir."""
        oturum = secrets.token_urlsafe(18)
        simdi = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO api_clients(key_id, oturum, ip, istemci, rol,"
                " ilk_gorulme, son_gorulme, istek_sayisi) VALUES(?,?,?,?,?,?,?,0)",
                (int(key_id), oturum, ip[:64], (istemci or "")[:120], rol, simdi, simdi),
            )
            self._conn.commit()
        return oturum

    def oturum_dokun(self, oturum: str, ip: str = "") -> dict | None:
        """Oturumu 'son gorulme' ile tazeler. Iptal edilmisse None doner."""
        if not oturum:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM api_clients WHERE oturum = ?", (oturum,)).fetchone()
            if row is None or row["iptal"]:
                return None
            self._conn.execute(
                "UPDATE api_clients SET son_gorulme = ?, istek_sayisi = istek_sayisi + 1,"
                " ip = COALESCE(NULLIF(?, ''), ip) WHERE oturum = ?",
                (time.time(), ip[:64], oturum),
            )
            self._conn.commit()
        return self._istemci_disa(row)

    def istemciler(self, dakika: int = 0) -> list[dict]:
        sql = ("SELECT c.*, k.ad AS anahtar_adi FROM api_clients c"
               " LEFT JOIN api_keys k ON k.id = c.key_id")
        args: tuple = ()
        if dakika > 0:
            sql += " WHERE c.son_gorulme >= ?"
            args = (time.time() - dakika * 60,)
        sql += " ORDER BY c.son_gorulme DESC LIMIT 200"
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [self._istemci_disa(r) for r in rows]

    def oturum_iptal(self, client_id: int) -> dict:
        with self._lock:
            self._conn.execute(
                "UPDATE api_clients SET iptal = 1 WHERE id = ?", (int(client_id),))
            self._conn.commit()
        return {"id": int(client_id), "iptal": True}

    def oturumlari_temizle(self, gun: int = 7) -> int:
        """Idempotent bakim: iptal edilmis ve eskimis oturum kayitlarini sil."""
        sinir = time.time() - gun * 86400
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM api_clients WHERE iptal = 1 AND son_gorulme < ?", (sinir,))
            self._conn.commit()
            return int(cur.rowcount or 0)

    @staticmethod
    def _istemci_disa(row) -> dict:
        veri = {
            "id": int(row["id"]),
            "key_id": row["key_id"],
            "ip": row["ip"],
            "istemci": row["istemci"],
            "rol": row["rol"],
            "ilk_gorulme": row["ilk_gorulme"],
            "son_gorulme": row["son_gorulme"],
            "istek_sayisi": int(row["istek_sayisi"] or 0),
            "iptal": bool(row["iptal"]),
        }
        try:
            veri["anahtar_adi"] = row["anahtar_adi"]
        except (IndexError, KeyError):
            veri["anahtar_adi"] = None
        return veri

    # --- sunucu profilleri ------------------------------------------------
    def profil_kaydet(self, ad: str, adres: str, port: int, originler: str = "",
                      istek_limiti: int = 120, profil_id: int = 0) -> dict:
        ad = (ad or "").strip()[:48]
        if not ad:
            raise ValueError("profil adi gerekli")
        adres = (adres or "yerel").strip().lower()
        if adres not in ("yerel", "lan"):
            raise ValueError("adres 'yerel' veya 'lan' olmali")
        port = int(port or 0)
        if not (1024 <= port <= 65535):
            raise ValueError("port 1024-65535 araliginda olmali")
        istek_limiti = max(1, min(100000, int(istek_limiti or 120)))
        originler = (originler or "").strip()[:500]
        with self._lock:
            if profil_id:
                self._conn.execute(
                    "UPDATE server_profiles SET ad=?, adres=?, port=?, originler=?,"
                    " istek_limiti=? WHERE id=?",
                    (ad, adres, port, originler, istek_limiti, int(profil_id)))
                kimlik = int(profil_id)
            else:
                cur = self._conn.execute(
                    "INSERT INTO server_profiles(ad, adres, port, originler,"
                    " istek_limiti, olusturuldu) VALUES(?,?,?,?,?,?)",
                    (ad, adres, port, originler, istek_limiti, time.time()))
                kimlik = int(cur.lastrowid)
            self._conn.commit()
        return {"id": kimlik, "ad": ad, "adres": adres, "port": port,
                "originler": originler, "istek_limiti": istek_limiti}

    def profil_sil(self, profil_id: int) -> dict:
        with self._lock:
            self._conn.execute(
                "DELETE FROM server_profiles WHERE id = ?", (int(profil_id),))
            self._conn.commit()
        if int(self.store.get("sunucu_profil_id") or 0) == int(profil_id):
            self.store.set("sunucu_profil_id", 0)
        return {"id": int(profil_id), "silindi": True}

    def profiller(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM server_profiles ORDER BY olusturuldu ASC").fetchall()
        etkin = int(self.store.get("sunucu_profil_id") or 0)
        return [{
            "id": int(r["id"]), "ad": r["ad"], "adres": r["adres"],
            "port": int(r["port"]), "originler": r["originler"] or "",
            "istek_limiti": int(r["istek_limiti"] or 120),
            "olusturuldu": r["olusturuldu"],
            "etkin": int(r["id"]) == etkin,
        } for r in rows]

    def profil(self, profil_id: int) -> dict | None:
        for p in self.profiller():
            if p["id"] == int(profil_id):
                return p
        return None


def ip_maskele(ip: str) -> str:
    """Olay kaydina yazilabilecek kadar kisitli IP gosterimi.

    Son sekizli gizlenir: 192.168.1.42 -> 192.168.1.x. Adres tam olarak
    yalnizca "aktif istemciler" ekraninda, yoneticiye gosterilir."""
    if not ip:
        return "?"
    if ":" in ip:  # IPv6
        parcalar = ip.split(":")
        return ":".join(parcalar[:3]) + ":x"
    parcalar = ip.split(".")
    if len(parcalar) == 4:
        return ".".join(parcalar[:3]) + ".x"
    return "?"
