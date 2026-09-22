# -*- coding: utf-8 -*-
"""UI'dan BAGIMSIZ servis katmani — v2.1 Headless Server.

Bu modul AfuDM'in is mantiginin TEK kapisidir. Masaustu arayuzu (pywebview
`Api`), yonetim web paneli (HTTP) ve CLI AYNI bu sinifi cagirir; hicbir yerde
kod kopyalanmaz. Sinif `webview` modulunu IMPORT ETMEZ ve pencereye
dokunmaz — pywebview kurulu olmayan bir makinede de calisir.

Isleyis kurallari:
* Uzun surebilecek isler (indirme baslatma, sondaj) zaten Manager'in kendi
  is parcaciklarinda doner; burada ek bir bloklama yapilmaz.
* Kalici isler idempotenttir: ayni anahtari iki kez iptal etmek, ayni profili
  iki kez silmek hata vermez.
* Hicbir metot token/parola/cerez DEGERINI doner veya loglar. Yalnizca
  `anahtar_olustur` ve `anahtar_rotasyon` gizli degeri BIR KEZ dondurur.
"""
from __future__ import annotations

import threading
import time

from . import erisim, kaydet, models, paths, surum
from .hata import AfuHata
from .erisim import ErisimDeposu, HizSinirlayici

# Bir ayarin ne zaman etkili oldugu. Arayuz bunu ROZET olarak gosterir;
# tek kaynak burasidir (UI tahmin yurutmez).
UYGULAMA_ZAMANI: dict[str, str] = {
    # hemen
    "max_speed_kb": "hemen",
    "hiz_profili": "hemen",
    "snail_speed_kb": "hemen",
    "max_concurrent": "hemen",
    "seed_ratio": "hemen",
    "clipboard_watch": "hemen",
    "clipboard_exts": "hemen",
    "language": "hemen",
    "notify_telegram": "hemen",
    "telegram_bot_token": "hemen",
    "telegram_chat_id": "hemen",
    "shutdown_when_done": "hemen",
    "sleep_when_done": "hemen",
    "sunucu_istek_limiti": "hemen",
    "sunucu_hatali_limit": "hemen",
    "sunucu_kilit_saniye": "hemen",
    "sunucu_istemci_kaydi": "hemen",
    "sunucu_proxy_guven": "hemen",
    # yeni indirmelerde
    "download_dir": "yeni_indirmelerde",
    "kategori_klasorleri": "yeni_indirmelerde",
    "video_quality": "yeni_indirmelerde",
    "kaydetme_penceresi": "yeni_indirmelerde",
    "proxy": "yeni_indirmelerde",
    "system_proxy": "yeni_indirmelerde",
    "split": "yeni_indirmelerde",
    "max_conn_per_server": "yeni_indirmelerde",
    # Ac/kapa dugmesi sunucuyu O ANDA baslatir/durdurur (bkz. sunucu_ayarla).
    "sunucu_acik": "hemen",
    # servis yeniden baslayinca
    "sunucu_port": "servis_yeniden",
    "sunucu_adres": "servis_yeniden",
    "sunucu_profil_id": "servis_yeniden",
    "lan_erisimi": "servis_yeniden",
    "api_port": "servis_yeniden",
    # sonraki baslatmada
    "tepsiye_kucult": "sonraki_baslatmada",
    "baslangicta_tepside": "sonraki_baslatmada",
    "auto_update_trackers": "sonraki_baslatmada",
    "tracker_otomatik_tara": "sonraki_baslatmada",
}


def uygulama_zamani(anahtar: str) -> str:
    """Bilinmeyen ayar icin 'hemen' UYDURMAYIZ: 'bilinmiyor' doneriz."""
    return UYGULAMA_ZAMANI.get(anahtar, "bilinmiyor")


class AfuDMServis:
    """Masaustu ve headless calisma icin ORTAK servis katmani."""

    def __init__(self, manager, kip: str = "masaustu") -> None:
        self.manager = manager
        self.store = manager.store
        self.kip = kip
        self.erisim = ErisimDeposu(self.store)
        self.limitci = HizSinirlayici(
            limit=int(self.store.get("sunucu_istek_limiti") or 120),
            hatali_limit=int(self.store.get("sunucu_hatali_limit") or 8),
            kilit_saniye=int(self.store.get("sunucu_kilit_saniye") or 300),
        )
        self.baslangic = time.time()
        # Yonetim sunucusu: `api.web.YonetimSunucusu` ornegi (veya None).
        # Tip bagimliligi yok: servis katmani HTTP'yi bilmek ZORUNDA degil.
        self.sunucu = None
        self._sunucu_hata = ""
        self._lock = threading.RLock()

    # ==================================================================
    # indirmeler
    # ==================================================================
    def liste(self, filtre: str = "", arama: str = "") -> dict:
        """Anlik durum. `filtre`: all|active|paused|video|torrent|complete|error."""
        snap = self.manager.snapshot()
        ogeler = snap.get("items", [])
        f = (filtre or "all").strip().lower()
        if f and f != "all":
            ogeler = [o for o in ogeler if self._filtreye_uyar(o, f)]
        ara = (arama or "").strip().lower()
        if ara:
            ogeler = [o for o in ogeler
                      if ara in str(o.get("title") or "").lower()
                      or ara in str(o.get("filename") or "").lower()
                      or ara in str(o.get("source") or "").lower()]
        snap["items"] = ogeler
        snap["ok"] = True
        return snap

    @staticmethod
    def _filtreye_uyar(oge: dict, f: str) -> bool:
        durum = str(oge.get("status") or "")
        tur = str(oge.get("kind") or "")
        if f == "active":
            return durum == "active"
        if f == "paused":
            return durum == "paused"
        if f == "complete":
            return durum == "complete"
        if f == "error":
            return durum == "error"
        if f in ("video", "torrent", "http"):
            return tur == f
        return True

    def hedef_klasor(self, secilen: str, url: str, kind: str, kategori: str, uzaktan: bool = False) -> str | None:
        """Ayar onceligi: ise ozel secim -> kategori kurali -> genel varsayilan."""
        if secilen:
            if uzaktan:
                import os
                from pathlib import Path
                try:
                    secilen_path = Path(secilen).resolve()
                    kok_path = Path(self.manager.current_download_dir()).resolve()
                    if not secilen_path.is_relative_to(kok_path):
                        raise AfuHata("hedef klasor izinli kok dizin disinda", code="HEDEF_DISARIDA")
                except ValueError:
                    raise AfuHata("gecersiz hedef klasor yolu", code="HEDEF_DISARIDA")
            return secilen
        if not self.store.get("kategori_klasorleri"):
            return None
        kategori = kategori or kaydet.kategori_tahmin(url, kind)
        return kaydet.kategori_klasoru(self.manager.current_download_dir(), kategori)

    def ekle(self, payload: dict) -> dict:
        """Bir veya daha cok link ekle. Kismi basari da RAPORLANIR.

        Doner: {ok, added, scheduled, failed:[...]}. `failed` bos degilse
        arayuz her satiri ayri gosterip yeniden denemeyi teklif eder.
        """
        payload = payload or {}
        urls = payload.get("urls")
        if not urls:
            tek = (payload.get("url") or payload.get("source") or "").strip()
            urls = [tek] if tek else []
        urls = [str(u).strip() for u in urls if str(u).strip()]
        if not urls:
            return {"ok": False, "code": "BAD_REQUEST", "error": "link gerekli"}
        try:
            start_after = models.parse_time_spec(payload.get("start_at", ""))
        except ValueError as exc:
            return {"ok": False, "code": "BAD_REQUEST", "error": str(exc)}
        tek_ad = (kaydet.guvenli_dosya_adi(payload.get("filename") or "")
                  if len(urls) == 1 else "")
        added, scheduled, failed = 0, 0, []
        for url in urls:
            try:
                kind = self.manager.detect_kind(url)
                self.manager.add(
                    url,
                    dest_dir=self.hedef_klasor(
                        payload.get("dest_dir") or "", url, kind,
                        payload.get("kategori") or "", bool(payload.get("_uzaktan"))),
                    filename=tek_ad if tek_ad and kind == "http" else None,
                    title=tek_ad if tek_ad and kind == "video" else None,
                    quality=payload.get("quality") or None,
                    audio_only=bool(payload.get("audio_only")),
                    playlist=bool(payload.get("playlist")),
                    start_after=start_after,
                    altyazi_diller=payload.get("altyazi_diller") or "",
                    oto_altyazi=bool(payload.get("oto_altyazi")),
                    altyazi_goem=bool(payload.get("altyazi_goem")),
                    kucuk_resim=payload.get("kucuk_resim") or "",
                    ustveri_goem=bool(payload.get("ustveri_goem")),
                    bolumler=payload.get("bolumler") or "",
                    sponsorblock=payload.get("sponsorblock") or "",
                    bolum_araligi=payload.get("bolum_araligi") or "",
                    kapsayici=payload.get("kapsayici") or "",
                    ses_formati=payload.get("ses_formati") or "",
                    dosya_sablonu=payload.get("dosya_sablonu") or "",
                    tarayici_cerezi=payload.get("tarayici_cerezi") or "",
                )
                if start_after:
                    scheduled += 1
                else:
                    added += 1
            except Exception as exc:
                failed.append(("%s: %s" % (url[:48], exc))[:180])
        if not added and not scheduled and failed:
            return {"ok": False, "code": "EKLENEMEDI", "error": failed[0],
                    "failed": failed}
        return {"ok": True, "added": added, "scheduled": scheduled, "failed": failed}

    def kontrol(self, action: str, gid: str = "", delete_files: bool = False) -> dict:
        """pause | resume | remove | pause_all | resume_all | ayarla."""
        eylem = (action or "").strip()
        try:
            if eylem == "pause":
                self.manager.pause(gid)
            elif eylem == "resume":
                self.manager.resume(gid)
            elif eylem == "remove":
                df = delete_files.get("delete_files", False) if isinstance(delete_files, dict) else delete_files
                try:
                    self.manager.remove(gid, bool(df))
                except Exception as rem_exc:
                    err_msg = str(rem_exc).lower()
                    if "kayit bulunamadi" in err_msg or "not found" in err_msg:
                        return {"ok": True, "action": "remove", "gid": gid, "orphan": True}
                    raise
            elif eylem == "pause_all":
                self.manager.pause_all()
            elif eylem == "resume_all":
                self.manager.resume_all()
            else:
                return {"ok": False, "code": "BILINMEYEN_EYLEM",
                        "error": "bilinmeyen eylem: %s" % eylem[:24]}
        except Exception as exc:
            err_msg = str(exc).lower()
            if eylem == "remove" and ("kayit bulunamadi" in err_msg or "not found" in err_msg):
                return {"ok": True, "action": "remove", "gid": gid, "orphan": True}
            return {"ok": False, "code": "ISLEM_HATASI", "error": str(exc)[:300]}
        return {"ok": True, "action": eylem, "gid": gid}

    def baglanti_ayarla(self, gid: str, baglanti=None, hiz_kb=None) -> dict:
        try:
            return {"ok": True, **self.manager.baglanti_ayarla(
                gid, baglanti=baglanti, hiz_kb=hiz_kb)}
        except Exception as exc:
            return {"ok": False, "code": "ISLEM_HATASI", "error": str(exc)[:300]}

    def yeniden_dene(self, row_id: int) -> dict:
        try:
            return {"ok": True, **self.manager.retry(int(row_id))}
        except Exception as exc:
            return {"ok": False, "code": "ISLEM_HATASI", "error": str(exc)[:300]}

    def yenile_link(self, gid: str, yeni_url: str, **kw) -> dict:
        try:
            return {"ok": True, **self.manager.renew(gid, yeni_url, **kw)}
        except Exception as exc:
            return {"ok": False, "code": "ISLEM_HATASI", "error": str(exc)[:300]}

    def bitmisleri_temizle(self) -> dict:
        return {"ok": True, "removed": self.store.clear_finished()}

    def olaylar(self, gid: str = "", limit: int = 60) -> dict:
        return {"ok": True,
                "events": self.store.recent_events(limit=max(1, min(500, int(limit))),
                                                   gid=gid or "")}

    # ==================================================================
    # ayarlar
    # ==================================================================
    def ayarlar(self) -> dict:
        """Tum ayarlar + her birinin UYGULANMA ZAMANI rozeti."""
        degerler = self.store.all_settings()
        return {
            "ok": True,
            "settings": degerler,
            "uygulama": {k: uygulama_zamani(k) for k in degerler},
        }

    def ayar_kaydet(self, payload: dict) -> dict:
        """Ayar yaz. Sunucuya ait ayarlar CANLI olarak limitciye de islenir."""
        payload = payload or {}
        try:
            ayarlar = self.manager.update_settings(payload)
        except Exception as exc:
            return {"ok": False, "code": "AYAR_HATASI", "error": str(exc)[:300]}
        self.limitleri_tazele()
        return {
            "ok": True,
            "settings": ayarlar,
            "uygulama": {k: uygulama_zamani(k) for k in payload},
            # Sunucuyu ilgilendiren ayar degistiyse arayuz "yeniden baslat"
            # rozetini gostersin diye acikca bildiriyoruz.
            "sunucu_yeniden_gerekli": any(
                uygulama_zamani(k) == "servis_yeniden" for k in payload),
        }

    def limitleri_tazele(self) -> None:
        """Etkin profil varsa istek limiti ONDAN gelir (profil > genel ayar).

        Arayuz etkin degerin kaynagini `sunucu_durumu().profil_ad` ile gosterir;
        iki ayri limitin sessizce catismasi diye bir sey olmaz."""
        self.limitci.ayarla(
            limit=int(self.sunucu_ayarlari()["istek_limiti"]),
            hatali_limit=int(self.store.get("sunucu_hatali_limit") or 8),
            kilit_saniye=int(self.store.get("sunucu_kilit_saniye") or 300),
        )

    def hiz_profili(self, ad: str) -> dict:
        try:
            return {"ok": True, **self.manager.set_mode(ad)}
        except Exception as exc:
            return {"ok": False, "code": "BAD_REQUEST", "error": str(exc)[:200]}

    # ==================================================================
    # yonetim sunucusu (HTTP)
    # ==================================================================
    def sunucu_ayarlari(self) -> dict:
        """Etkin profil varsa ONUN degerleri, yoksa genel ayarlar."""
        profil_id = int(self.store.get("sunucu_profil_id") or 0)
        profil = self.erisim.profil(profil_id) if profil_id else None
        if profil:
            return {"adres": profil["adres"], "port": profil["port"],
                    "originler": profil["originler"],
                    "istek_limiti": profil["istek_limiti"],
                    "profil_id": profil["id"], "profil_ad": profil["ad"]}
        return {
            "adres": str(self.store.get("sunucu_adres") or "yerel"),
            "port": int(self.store.get("sunucu_port") or 6821),
            "originler": str(self.store.get("sunucu_izinli_originler") or ""),
            "istek_limiti": int(self.store.get("sunucu_istek_limiti") or 120),
            "profil_id": 0, "profil_ad": "",
        }

    def sunucu_baslat(self) -> dict:
        """Yonetim sunucusunu ac. Idempotent: zaten aciksa mevcut durumu doner."""
        with self._lock:
            if self.sunucu is not None and self.sunucu.calisiyor:
                return {"ok": True, "zaten": True, **self.sunucu_durumu()["sunucu"]}
            from api.web import YonetimSunucusu  # gec import: dongu olmasin
            ayar = self.sunucu_ayarlari()
            try:
                self.sunucu = YonetimSunucusu(self, ayar["adres"], ayar["port"])
                self.sunucu.start()
                self._sunucu_hata = ""
            except Exception as exc:
                self._sunucu_hata = str(exc)[:300]
                self.sunucu = None
                self.store.log("error", "yonetim sunucusu acilamadi: %s"
                               % self._sunucu_hata)
                return {"ok": False, "code": "SUNUCU_ACILAMADI",
                        "error": self._sunucu_hata}
            self.store.set("sunucu_acik", True)
            self.store.log("info", "yonetim sunucusu acildi (port %d)" % self.sunucu.port)
            return {"ok": True, **self.sunucu_durumu()["sunucu"]}

    def sunucu_durdur(self) -> dict:
        """Idempotent: kapaliyken cagirmak hata degildir."""
        with self._lock:
            if self.sunucu is not None:
                try:
                    self.sunucu.stop()
                except Exception as exc:
                    self._sunucu_hata = str(exc)[:300]
                self.sunucu = None
            self.store.set("sunucu_acik", False)
            self.store.log("info", "yonetim sunucusu kapatildi")
            return {"ok": True, "calisiyor": False}

    def sunucu_yeniden(self) -> dict:
        self.sunucu_durdur()
        return self.sunucu_baslat()

    def sunucu_ayarla(self, acik: bool) -> dict:
        """Tek anahtar: ac/kapa. Arayuzdeki anahtar dugmesi bunu cagirir."""
        return self.sunucu_baslat() if acik else self.sunucu_durdur()

    def sunucu_durumu(self) -> dict:
        ayar = self.sunucu_ayarlari()
        calisiyor = bool(self.sunucu is not None and self.sunucu.calisiyor)
        bilgi = {
            "calisiyor": calisiyor,
            "istenen": bool(self.store.get("sunucu_acik")),
            "adres": ayar["adres"],
            "port": self.sunucu.port if calisiyor else ayar["port"],
            "url": self.sunucu.panel_url() if calisiyor else "",
            "lan_url": self.sunucu.lan_url() if calisiyor else "",
            "profil_id": ayar["profil_id"],
            "profil_ad": ayar["profil_ad"],
            "hata": self._sunucu_hata,
            "istek_sayisi": self.sunucu.istek_sayisi if calisiyor else 0,
            "reddedilen": self.sunucu.reddedilen if calisiyor else 0,
            "baslangic": self.sunucu.baslangic if calisiyor else 0,
        }
        return {"ok": True, "sunucu": bilgi, "limit": self.limitci.durum()}

    def durum(self) -> dict:
        """Servis + motor + sunucu tek bakista (CLI `server status` bunu basar)."""
        from . import engines
        snap = self.manager.snapshot()
        aktif = sum(1 for o in snap.get("items", [])
                    if str(o.get("status")) == "active")
        return {
            "ok": True,
            "app": "AfuDM",
            "surum": surum.SURUM,
            "kip": self.kip,
            "calisma_suresi": round(time.time() - self.baslangic, 1),
            "motor": engines.durum(),
            "aktif_indirme": aktif,
            "toplam_indirme": len(snap.get("items", [])),
            "hiz": snap.get("speed", 0),
            "klasor": str(paths.BASE),
            "indirme_klasoru": self.manager.current_download_dir(),
            **self.sunucu_durumu(),
        }

    # ==================================================================
    # erisim anahtarlari / istemciler / profiller
    # ==================================================================
    def anahtarlar(self) -> dict:
        return {"ok": True, "roller": list(erisim.ROLLER),
                "anahtarlar": self.erisim.anahtarlar()}

    def anahtar_olustur(self, ad: str, rol: str, not_metni: str = "") -> dict:
        """Gizli deger SADECE bu yanitta gelir; bir daha gosterilemez."""
        try:
            return {"ok": True, **self.erisim.anahtar_olustur(ad, rol, not_metni)}
        except ValueError as exc:
            return {"ok": False, "code": "BAD_REQUEST", "error": str(exc)}

    def anahtar_rotasyon(self, key_id: int) -> dict:
        try:
            return {"ok": True, **self.erisim.anahtar_rotasyon(int(key_id))}
        except ValueError as exc:
            return {"ok": False, "code": "BAD_REQUEST", "error": str(exc)}

    def anahtar_iptal(self, key_id: int) -> dict:
        try:
            return {"ok": True, **self.erisim.anahtar_iptal(int(key_id))}
        except ValueError as exc:
            return {"ok": False, "code": "BAD_REQUEST", "error": str(exc)}

    def anahtar_sil(self, key_id: int) -> dict:
        return {"ok": True, **self.erisim.anahtar_sil(int(key_id))}

    def anahtar_rol_ayarla(self, key_id: int, rol: str) -> dict:
        try:
            return {"ok": True, **self.erisim.anahtar_rol_ayarla(int(key_id), rol)}
        except ValueError as exc:
            return {"ok": False, "code": "BAD_REQUEST", "error": str(exc)}

    def istemciler(self, dakika: int = 0) -> dict:
        return {"ok": True, "istemciler": self.erisim.istemciler(int(dakika or 0))}

    def istemci_iptal(self, client_id: int) -> dict:
        sonuc = self.erisim.oturum_iptal(int(client_id))
        self.store.log("info", "istemci oturumu iptal edildi (#%d)" % int(client_id))
        return {"ok": True, **sonuc}

    def istemcileri_temizle(self, gun: int = 7) -> dict:
        return {"ok": True, "silinen": self.erisim.oturumlari_temizle(int(gun))}

    def kilitleri_temizle(self) -> dict:
        """Kaba kuvvet kilidine takilan IP'leri elle serbest birak."""
        return {"ok": True, "temizlenen": self.limitci.kilitleri_temizle()}

    def profiller(self) -> dict:
        return {"ok": True, "profiller": self.erisim.profiller(),
                "etkin": int(self.store.get("sunucu_profil_id") or 0)}

    def profil_kaydet(self, veri: dict) -> dict:
        veri = veri or {}
        try:
            sonuc = self.erisim.profil_kaydet(
                ad=veri.get("ad") or "",
                adres=veri.get("adres") or "yerel",
                port=veri.get("port") or 0,
                originler=veri.get("originler") or "",
                istek_limiti=veri.get("istek_limiti") or 120,
                profil_id=int(veri.get("id") or 0),
            )
        except (ValueError, TypeError) as exc:
            return {"ok": False, "code": "BAD_REQUEST", "error": str(exc)}
        return {"ok": True, **sonuc,
                "sunucu_yeniden_gerekli": int(self.store.get("sunucu_profil_id") or 0)
                == sonuc["id"]}

    def profil_sil(self, profil_id: int) -> dict:
        return {"ok": True, **self.erisim.profil_sil(int(profil_id))}

    def profil_etkinlestir(self, profil_id: int) -> dict:
        """0 = profil kullanma (genel ayarlara don). Etki: servis yeniden baslayinca."""
        profil_id = int(profil_id or 0)
        if profil_id and self.erisim.profil(profil_id) is None:
            return {"ok": False, "code": "BAD_REQUEST", "error": "profil bulunamadi"}
        self.store.set("sunucu_profil_id", profil_id)
        return {"ok": True, "etkin": profil_id, "sunucu_yeniden_gerekli": True}

    # ==================================================================
    # yetenek bildirimi
    # ==================================================================
    def yetenekler(self) -> dict:
        """/capabilities — YALNIZCA gercekten calisan ozellikleri bildirir.

        Her girdi bu surumde uctan uca (backend + arayuz) dogrulanabilir bir
        ozelliktir. Calismayan hicbir sey buraya yazilmaz."""
        from . import engines
        ozellikler = [
            "scheduler", "hiz_profilleri", "renew", "ozel_basliklar", "cerez",
            "zamanlama", "cli", "api", "kategori_klasorleri", "proxy",
            "sistem_proxy", "checksum", "canli_ayar",
            # v2.1 Headless Server
            "headless", "servis_katmani", "web_panel", "roller",
            "erisim_anahtarlari", "anahtar_rotasyonu", "aktif_istemciler",
            "hiz_sinirlama", "origin_denetimi", "sunucu_profilleri",
            "tek_ornek_kilidi",
        ]
        return {
            "ok": True,
            "app": "AfuDM",
            "surum": surum.SURUM,
            "api": 2,
            "kip": self.kip,
            "uzanti_surumu": surum.uzanti_surumu(),
            "motorlar": engines.durum(),
            "protokoller": ["http", "https", "ftp", "sftp", "magnet", "torrent"],
            "turler": ["http", "video", "torrent"],
            "roller": list(erisim.ROLLER),
            "ozellikler": ozellikler,
            "sinirlar": {
                "kaynak": models.SOURCE_MAX,
                "baslik": models.TITLE_MAX,
                "user_agent": models.USER_AGENT_MAX,
                "ozel_baslik": models.HEADER_COUNT_MAX,
                "proxy": models.PROXY_MAX,
            },
        }
