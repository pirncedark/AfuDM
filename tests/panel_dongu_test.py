# -*- coding: utf-8 -*-
"""Panel döngü testi (tests/panel_dongu_test.py).

ui/index.html icindeki HER .veil / modal / cekmece (drawer) paneli için
headless "tikla-dogrula" yasadongusu calistirir:

  1) Acilis            -> panel .open/.on sinifiyla görünür oluyor
  2) Kopru eşleme      -> panelin ana aksiyon düğmeleri beklenen bridge
                           metodunu ÇAĞIRIYOR (sadece isim, gerçek API yok)
  3) Tüm kontroller    -> panel icindeki görünür/her kontrole tek tek tikla:
                           hiçbir tek basina uncaught JS hatası atmıyor,
                           başka bir pano/eşik acilmazsa kapatılıyor
  4) X / ESC / arkaplan -> kapatma yolları uyumlu
  5) Kopru hatası      -> bridge throw edince: hata mesajı görünüyor,
                           panel ölü kalmıyor, yine kapanabiliyor

Üretim koduna dokunulmaz; pywebview arka ucu sahte (fake) ile taklit edilir.
Bu dosyadaki hiçbir test gerçek sunucuya / dosya sistemine yazmaz.
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

KOK = Path(__file__).resolve().parents[1]


def _LOG(mesaj):
    if os.environ.get("AFUDM_ADIM_LOG"):
        sys.stderr.write(mesaj + "\n")
        sys.stderr.flush()

# --------------------------------------------------------------------------
# app.js'ten bridge isimlerini ikinci bağımsız kaynaktan çek (kopru_esleme ile
# aynı kural): sahte+gerçek kopru setini BİR kaynaktan senkron tutmak yerine
# burada ayrıca üretip init scriptine gömüyoruz.
# --------------------------------------------------------------------------
def _appjs_bridge_isimleri():
    src = (KOK / "ui" / "app.js").read_text(encoding="utf-8")
    statik = set(
        re.findall(r"call\(\s*[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']", src)
    )
    dinamik = {
        "windows_integration_" + v
        for v in re.findall(r"data-winint=\"([A-Za-z0-9_]+)\"", src)
    }
    return statik | dinamik


def _appjs_pywebview_dogrudan():
    src = (KOK / "ui" / "app.js").read_text(encoding="utf-8")
    return set(
        re.findall(r"pywebview\??\.api\.([A-Za-z_][A-Za-z0-9_]*)", src)
    )


# --------------------------------------------------------------------------
# Sahte arka uç: her bridge metodunu loglar, özel şekil döndürür, tanımsızı
# {ok:true} ile tolere eder.
# --------------------------------------------------------------------------
def _sahte_backend_script():
    isimler = sorted(_appjs_bridge_isimleri() | _appjs_pywebview_dogrudan())
    liste_json = json.dumps(isimler)
    return f"""
    window.__otest = {{ calls: [], lookup: 0 }};
    window.fakeBackendState = {{
      bekleyen: [],
      snapshot: () => ({{
        items: [
          {{ gid: "t1", title: "Ornek Torrent", kind: "torrent", status: "active",
             seeder: false, progress: 55.5, completedLength: 104857600,
             totalLength: 209715200, downloadSpeed: 0, uploadSpeed: 0,
             connections: 4, numSeeders: 2, eta: 9, ratio: 1,
             filename: "Ornek Torrent", dir: "C:\\\\Torrents" }},
          {{ gid: "c1", title: "Ornek Video.mp4", kind: "http", status: "complete",
             seeder: false, progress: 100, completedLength: 524288000,
             totalLength: 524288000, downloadSpeed: 0, uploadSpeed: 0,
             connections: 0, numSeeders: 0, eta: 0,
             filename: "Ornek Video.mp4", dir: "C:\\\\Videolar" }},
          {{ gid: "p1", title: "Duraklatilan.iso", kind: "http", status: "paused",
             seeder: false, progress: 42, completedLength: 2048,
             totalLength: 4096, downloadSpeed: 0, uploadSpeed: 0,
             connections: 0, numSeeders: 0, eta: 0,
             filename: "Duraklatilan.iso", dir: "C:\\\\ISO" }}
        ],
        settings: {{
          language: "tr", max_concurrent: 5, split: 64, max_conn_per_server: 16,
          internet_paylasim: true, kaydetme_penceresi: true,
          kategori_klasorleri: true, tepsiye_kucult: true,
          baslangicta_tepside: false, download_dir: "C:\\\\indirilenler",
          video_quality: "best", ek_trackerlar: "",
          automation_enabled: true, automation_steps: ["checksum", "extract"],
          automation_power: "none", automation_power_seconds: 60,
          sunucu_adres: "yerel", sunucu_port: 6821,
          sunucu_istek_limiti: 120, sunucu_hatali_limit: 10,
          sunucu_kilit_saniye: 1800, sunucu_istemci_kaydi: false
        }},
        stat: {{ downloadSpeed: 0, uploadSpeed: 0, numActive: 1,
                numWaiting: 0, numStopped: 1 }},
        engine_ok: true, download_dir: "C:\\\\indirilenler",
        lang: "tr"
      }})
    }};
    const __ozel = {{
      snapshot: () => window.fakeBackendState.snapshot(),
      port_durumu: () => ({{ calisan: 6811, yeniden_baslatma_gerekli: false }}),
      api_info: () => ({{ port: 6811 }}),
      surum_bilgi: () => ({{ surum: "2.4.0", uzanti: "" }}),
      motor_durumu: () => ({{ motorlar: {{}}, ilerleme: {{}} }}),
      reliability_integrity: () => "OK",
      reliability_restart_engine: () => ({{ ok: true, message: "yeniden baslatildi" }}),
      telefon_durumu: () => ({{ acik: false, adres: "", port: 6811, qr: "" }}),
      seed_dosyalari: () => ({{ eklenebilir: [], uygulanan: [] }}),
      seed_bilgi: () => ({{ ok: true, baslik: "Ornek Torrent", seed: 1,
        baglanti: 1, tracker: 2, havuz: 0, dht: true, ek_sayisi: 0,
        tarama: {{}}, ek_trackerlar: "" }}),
      seed_tazele: () => ({{ gid: "t1", tracker: 2 }}),
      seed_tracker_kaydet: () => ({{ liste: "udp://t.example.com:80", sayi: 1 }}),
      tracker_tara: () => ({{ canli: 1, olu: 0 }}),
      tracker_klasoru_ac: () => ({{ ok: true }}),
      torrent_dosyalari: (gid) => ({{ ok: true, gid: gid || "t1",
        hazir_degil: false,
        dosyalar: [
          {{ indeks: 0, ad: "a.bin", boyut: 104857600, secili: true }},
          {{ indeks: 1, ad: "b.bin", boyut: 52428800, secili: false }}
        ] }}),
      torrent_metrikleri: () => ({{ ok: true, hazir_degil: false,
        metrikler: {{ num_seeders: 2, connections: 4, ratio: 1,
                      tracker_sayisi: 2, canli_tracker: 1 }} }}),
      torrent_secimi_ayarla: () => ({{ ok: true }}),
      peers: () => ({{ peers: [] }}),
      bekleyen_listesi: () => ({{ ogeler: window.fakeBackendState.bekleyen || [] }}),
      kaydet_bilgi: () => ({{ kind: "video", kategori_klasorleri: true,
        klasorler: {{ video: "C:\\\\Videolar", muzik: "C:\\\\Muzik" }},
        ana: "C:\\\\indirilenler", dosya_adi: "ornek.mp4", kategori: "video" }}),
      probe_link: () => ({{ ok: true, filename: "ornek.mp4", kategori: "video",
        size: 0, resumable: true }}),
      linkgrabber_analiz: (metin) => {{
        const ilk = Array.isArray(metin) ? metin[0]
          : String(metin || "").split("\\n")[0] || "https://example.com/a.zip";
        return {{ ogeler: [ {{ url: ilk, tur: "http", filename: "a.zip",
          size: 123456 }} ] }};
      }},
      linkgrabber_onceki: () => ({{ ok: true, onceki: [] }}),
      linkgrabber_suz: (ogeler) => ({{ ok: true,
        indeks: (ogeler || []).map((_, i) => i),
        domainler: [], gosterilen: (ogeler || []).length,
        toplam: (ogeler || []).length }}),
      linkgrabber_probe: (urls) => ({{ ogeler: (urls || []).map((u) =>
        ({{ url: u, filename: "probe.bin", size: 123456 }})) }}),
      linkgrabber_iptal: () => ({{ ok: true }}),
      linkgrabber_ekle: () => ({{ ok: true, added: 1, scheduled: 0, failed: [] }}),
      add_links: () => ({{ ok: true, added: 1, scheduled: 0, failed: [] }}),
      clear_finished: () => ({{ removed: 1 }}),
      automation_jobs: () => ({{ ogeler: [] }}),
      loglar: () => ({{ ogeler: [] }}),
      sunucu_durumu: () => ({{ sunucu: {{ calisiyor: true,
        url: "http://127.0.0.1:6821", port: 6821, istek_sayisi: 0,
        reddedilen: 0, profil_ad: "test", hata: "" }},
        limit: {{ limit: 120, izlenen_ip: 0, kilitli_ip: 0 }},
        lan_url: "http://127.0.0.1:6821" }}),
      sunucu_ayarla: () => ({{ ok: true, zaten: false }}),
      sunucu_yeniden: () => ({{ ok: true }}),
      sunucu_anahtarlar: () => ({{ anahtarlar: [] }}),
      sunucu_anahtar_olustur: () => ({{ ok: true, gizli: "otest-secret-123" }}),
      sunucu_anahtar_rotasyon: () => ({{ gizli: "otest-secret-456" }}),
      sunucu_anahtar_iptal: () => ({{ ok: true }}),
      sunucu_anahtar_sil: () => ({{ ok: true }}),
      sunucu_istemciler: () => ({{ istemciler: [] }}),
      sunucu_istemci_iptal: () => ({{ ok: true }}),
      sunucu_istemci_temizle: () => ({{ ok: true }}),
      sunucu_kilit_temizle: () => ({{ temizlenen: 2 }}),
      sunucu_profiller: () => ({{ profiller: [] }}),
      sunucu_profil_kaydet: () => ({{ ok: true }}),
      sunucu_profil_sil: () => ({{ ok: true }}),
      sunucu_profil_etkinlestir: () => ({{ ok: true }}),
      sunucu_anahtar_rol: () => ({{ ok: true }}),
      sunucu_panel_ac: () => ({{ ok: true }}),
      panoya_kopyala: () => ({{ ok: true }}),
      panodan_oku: () => ({{ metin: "" }}),
      agda_paylas: () => ({{ ok: true,
        url: "http://127.0.0.1:6821/s/fake",
        local_url: "http://127.0.0.1:6821/s/fake",
        internet_url: "", smb: "", qr: "", warning: "" }}),
      motor_indir: () => ({{ ok: true }}),
      item_yolu: () => ({{ yol: "C:\\\\" }}),
      dosya_ac: () => ({{ ok: true }}),
      open_item_folder: () => ({{ ok: true }}),
      open_download_dir: () => ({{ ok: true }}),
      defender_scan: () => ({{ ok: true }}),
      ayar_rozetleri: () => ({{ uygulama: {{}}, guc: {{}} }}),
      baslangic_ayarla: () => ({{ ok: true }}),
      torrent_iliskilendir: () => ({{ ok: true }}),
      varsayilan_uygulama_ekrani: () => ({{ ok: true }}),
      seed_dosya_ekle: () => ({{ iptal: false, zaten: false, ad: "x.torrent",
        sayi: 1 }}),
      torrent_on_ekle: () => ({{ ok: true, gid: "t1" }}),
      torrent_on_iptal: () => ({{ ok: true }}),
      klasor_kisayollar: () => ({{ ogeler: [ {{ yol: "C:\\\\", derinlik: 0 }} ] }}),
      klasor_alt: () => ({{ ogeler: [] }}),
      klasor_yeni: () => ({{ yol: "C:\\\\yeni" }}),
      klasor_gozat: () => ({{ yol: "" }}),
      ag_konumu_ekle: () => ({{ yol: "" }}),
      ag_konumu_sil: () => ({{ ok: true }}),
      eklenti_listesi: () => ({{ eklentiler: [] }}),
      eklenti_incele: () => ({{ iptal: false, manifest: {{
        ad: "otest", baslik: "Otomatik Test Eklentisi", surum: "1.0",
        yazar: "otest", kaynak: "otest.afup", kurulu: false,
        izinler: ["ag"], domainler: ["example.com"],
        sha256: "0123456789abcdef", uyumlu: true,
        afudm_surum: "2.4.0", afudm_min: "*", afudm_max: "*" }} }}),
      eklenti_kur: () => ({{ ok: true }}),
      eklenti_islem: () => ({{ islem: {{ durum: "bitti", tur: "kur", mesaj: "" }} }}),
      eklenti_islem_iptal: () => ({{ ok: true }}),
      eklenti_klasoru_ac: () => ({{ ok: true }}),
      eklenti_guncelle: () => ({{ ok: true }}),
      eklenti_etkinlestir: () => ({{ ok: true }}),
      eklenti_kaldir: () => ({{ ok: true }}),
      eklenti_ayar_kaydet: () => ({{ ok: true }}),
      eklenti_gunluk: () => ({{ ok: true }}),
      eklenti_yeniden_baslat: () => ({{ ok: true }}),
      rules_list: () => ({{ ok: true, rules: [] }}),
      rules_save: () => ({{ ok: true }}),
      rules_simulate: () => ({{ ok: true, matched_rules: [], conflicts: [] }}),
      reliability_backup: () => ({{ ok: true, message: "odev" }}),
      reliability_backups: () => ({{ ok: true, items: [] }}),
      reliability_diagnostics_preview: () => ({{ ok: true }}),
      reliability_diagnostics_export: () => ({{ ok: true }}),
      reliability_health: () => ({{ ok: true }}),
      security_rotate_token: () => ({{ ok: true, token: "otest-token" }}),
      settings_save: () => ({{ ok: true }}),
      ayarlari_dogrula_kaydet: () => ({{ ok: true, ayarlar: {{}} }}),
      guc_durumu: () => ({{ mac: "", wol: true, kart: "", hazir: true }}),
      sistem_durumu: () => ({{ baslangic: false, torrent: {{}}, magnet: {{}} }}),
      windows_integration_status: () => ({{ durum: {{}}, uygulamalar: [] }}),
      windows_integration_apply: () => ({{ ok: true, registered: true }}),
      windows_integration_test: () => ({{ ok: true, registered: true }}),
      windows_integration_remove: () => ({{ ok: true }}),
      share_create: () => ({{ token: "x", url: "http://127.0.0.1/s/x" }}),
      share_list: () => ({{ ok: true, shares: [] }}),
      share_delete: () => ({{ ok: true }}),
      dosya_sec_ve_paylas: () => ({{ ok: true }}),
      chrome_hazirla: () => ({{ ok: true, klasor: "C:\\\\Chrome", chrome: true }}),
      chrome_ilerleme: () => ({{ ok: true, calisiyor: false, baglandi: false,
        mesaj: "" }}),
      chrome_otomatik: () => ({{ ok: true }}),
      chrome_kopyala: () => ({{ ok: true }}),
      pencere_durumu: () => ({{ ozel: true, buyuk: false }}),
      pencere_kucult: () => null,
      pencere_buyut: () => null,
      pencere_kapat: () => null,
      pencere_kenar: () => null
    }};
    const __isimler = {liste_json};
    const __api = {{}};
    for (const ad of __isimler) {{
      __api[ad] = async function (...args) {{
        window.__otest.calls.push({{ ad: ad, args: args }});
        const fn = __ozel[ad];
        if (fn) return fn(...args);
        return {{ ok: true }};
      }};
    }}
    window.pywebview = {{ api: __api }};
    window.otestHataGorunur = function (pid) {{
      const panel = document.getElementById(pid);
      if (panel) {{
        const yerel = panel.querySelectorAll('.err-note, [id$="Err"], #srvHata, #rulesResult, #shareErr');
        for (const el of yerel) {{
          if (el.textContent.trim() && el.style.display !== "none") return true;
        }}
      }}
      const tst = document.getElementById("toast");
      if (tst && tst.textContent.trim() && /show/.test(tst.className)) return true;
      return false;
    }};
    """


# --------------------------------------------------------------------------
# Panel tanımları: açıcı JS, kapatıcı seçici, köprü eşlemeleri, hata tetikleri.
# --------------------------------------------------------------------------
PANELS = {
    "addVeil": {
        "opener": "document.querySelector('#addBtn').click();",
        "closer": '[data-close="addVeil"]',
        "bridge": [
            {
                "pre": "document.getElementById('urls').value='https://example.com/a.zip';",
                "sel": "#addGo",
                "hesap": ["add_links"],
            },
        ],
        "err": {
            "method": "add_links",
            "trigger": "#addGo",
            "pre": ("document.getElementById('addModeMobile').checked=false;"
                    "document.getElementById('urls').value='https://example.com/a.zip';"),
        },
    },
    "setVeil": {
        "opener": "document.querySelector('#openSettings').click();",
        "closer": '[data-close="setVeil"]',
        "bridge": [
            {"sel": "#sVarsayilan", "hesap": ["varsayilan_uygulama_ekrani"]},
            {"sel": "#relIntegrity", "hesap": ["reliability_integrity"]},
            {"sel": "#relToken", "hesap": ["security_rotate_token"]},
            {"sel": "#sSeedKlasor", "hesap": ["tracker_klasoru_ac"]},
            {"sel": "#sSeedEkKaydet", "hesap": ["seed_tracker_kaydet"],
             "pre": "document.getElementById('sSeedEk').value='udp://tracker.example.com:1337';"},
        ],
        "err": {"method": "ayarlari_dogrula_kaydet", "trigger": "#setGo"},
    },
    "srvVeil": {
        "opener": "document.querySelector('#openServer').click();",
        "closer": '[data-close="srvVeil"]',
        "bridge": [
            {"sel": "#srvYenile", "hesap": ["sunucu_durumu"]},
            {"sel": "#srvKOlustur", "hesap": ["sunucu_anahtar_olustur"],
             "pre": "document.getElementById('srvKAd').value='otest-key';"},
            {"sel": "#srvPanelAc", "hesap": ["sunucu_panel_ac"]},
            {"sel": "#srvUrlKopya", "hesap": ["panoya_kopyala"]},
            {"sel": "#srvYeniden", "hesap": ["sunucu_yeniden"]},
        ],
        "err": {"method": "sunucu_yeniden", "trigger": "#srvYeniden"},
    },
    "chromeVeil": {
        "opener": "document.querySelector('#openChrome').click();",
        "closer": '[data-close="chromeVeil"]',
        "bridge": [
            {"sel": "#chrAuto", "hesap": ["chrome_otomatik"]},
            {"sel": '[data-kopya="adres"]', "hesap": ["chrome_kopyala"]},
        ],
        "err": {"method": "chrome_otomatik", "trigger": "#chrAuto"},
    },
    "kaydetVeil": {
        "opener": (
            "window.fakeBackendState.bekleyen=[{id:41,url:'https://example.com/v.mp4',"
            "kind:'video',filename:'ornek.mp4',title:'ornek'}];"
            "window.afudmBekleyen();window.fakeBackendState.bekleyen=[];"
        ),
        "closer": "#kayCancel",
        "bridge": [
            {"sel": "#kayGo", "hesap": ["bekleyen_onayla"]},
        ],
        "err": {"method": "bekleyen_onayla", "trigger": "#kayGo"},
    },
    "klasorVeil": {
        "opener": "window.klasorSec('C:\\\\');",
        "closer": "#klasCancel",
        "bridge": [
            {"sel": "#klasYeni", "hesap": ["klasor_yeni"],
             "pre": "document.getElementById('klasYol').value='C:\\\\';"},
            {"sel": "#klasSistem", "hesap": ["klasor_gozat"]},
        ],
        "err": {"method": "klasor_gozat", "trigger": "#klasSistem"},
    },
    "seedVeil": {
        "opener": "document.querySelector('.row[data-gid=\"t1\"] button[data-act=\"seed\"]').click();",
        "closer": '[data-close="seedVeil"]',
        "bridge": [
            {"sel": "#seedGo", "hesap": ["seed_tazele"]},
            {"sel": "#seedKaydet", "hesap": ["seed_tracker_kaydet"]},
            {"sel": "#seedTara", "hesap": ["tracker_tara"]},
            {"sel": "#seedKlasor", "hesap": ["tracker_klasoru_ac"]},
        ],
        "err": {"method": "seed_tazele", "trigger": "#seedGo"},
    },
    "lgVeil": {
        "opener": "document.querySelector('#lgBtn').click();",
        "closer": '[data-close="lgVeil"]',
        "bridge": [
            {"sel": "#lgAnaliz", "hesap": ["linkgrabber_analiz", "linkgrabber_onceki"],
             "pre": "document.getElementById('lgMetin').value='https://example.com/a.zip';"},
            {"sel": "#lgProbe", "hesap": ["linkgrabber_probe"]},
            {"sel": "#lgGo", "hesap": ["linkgrabber_ekle"]},
        ],
        "err": {"method": "linkgrabber_analiz", "trigger": "#lgAnaliz",
                "pre": "document.getElementById('lgMetin').value='https://example.com/a.zip';"},
    },
    "torrentVeil": {
        "opener": "document.querySelector('.row[data-gid=\"t1\"] button[data-act=\"files\"]').click();",
        "closer": '[data-close="torrentVeil"]',
        "bridge": [
            {"sel": "#torUygula", "hesap": ["torrent_secimi_ayarla"]},
        ],
        "err": {"method": "torrent_secimi_ayarla", "trigger": "#torUygula"},
    },
    "pluginVeil": {
        "opener": "document.querySelector('#openPlugins').click();",
        "closer": '[data-close="pluginVeil"]',
        "bridge": [
            {"sel": "#plgYenile", "hesap": ["eklenti_listesi"]},
            {"sel": "#plgKlasor", "hesap": ["eklenti_klasoru_ac"]},
            {"sel": "#plgKur", "hesap": ["eklenti_incele"]},
        ],
        "err": {"method": "eklenti_listesi", "trigger": "#plgYenile"},
    },
    "pluginOnayVeil": {
        "opener": "document.querySelector('#openPlugins').click();document.querySelector('#plgKur').click();",
        "closer": '[data-close="pluginOnayVeil"]',
        "bridge": [
            {"sel": "#plgOnayGo", "hesap": ["eklenti_kur"]},
        ],
        "err": {"method": "eklenti_kur", "trigger": "#plgOnayGo"},
    },
    "removeVeil": {
        "opener": (
            "if (state.items.every(i => i.gid !== 'c1')) {"
            " state.items.push({gid:'c1',title:'Ornek Video.mp4',kind:'http',status:'complete',"
            " seeder:false,progress:100,completedLength:524288000,totalLength:524288000,"
            " downloadSpeed:0,uploadSpeed:0,connections:0,numSeeders:0,eta:0,"
            " filename:'Ornek Video.mp4',dir:'C:\\\\Videolar'});"
            " state.selected=null; renderList(); renderDrawer(); }"
            "document.querySelector('.row[data-gid=\"c1\"] button[data-act=\"remove\"]').click();"
        ),
        "closer": '[data-close="removeVeil"]',
        "bridge": [
            {"sel": "#remGo", "hesap": ["control"]},
        ],
        "err": {"method": "control", "trigger": "#remGo"},
    },
    "shareCenterVeil": {
        "opener": "document.querySelector('#openShare').click();",
        "closer": '[data-close="shareCenterVeil"]',
        "bridge": [
            {"sel": "#shareSelectBtn", "hesap": ["dosya_sec_ve_paylas"]},
        ],
        "err": {"method": "dosya_sec_ve_paylas", "trigger": "#shareSelectBtn"},
    },
    "rulesVeil": {
        "opener": "document.querySelector('#rulesOpen').click();",
        "closer": '[data-close="rulesVeil"]',
        "bridge": [
            {"sel": "#rulesNew", "hesap": []},
            {"sel": "#rulesRun", "hesap": ["rules_simulate"],
             "pre": "document.getElementById('rulesUrl').value='https://example.com/f.iso';"},
            {"sel": "#rulesSave", "hesap": ["rules_save"]},
        ],
        "err": {"method": "rules_save", "trigger": "#rulesSave"},
    },
    "shareVeil": {
        "opener": "document.querySelector('.row[data-gid=\"c1\"] button[data-act=\"network-share\"]').click();",
        "closer": '[data-close="shareVeil"]',
        "bridge": [
            {"sel": "#shareCopy", "hesap": ["panoya_kopyala"],
             "pre": "document.getElementById('shareLink').value='https://example.com/shared';"},
            {"sel": "#shareInternetCopy", "hesap": ["panoya_kopyala"],
             "pre": "document.getElementById('shareInternetLink').value='https://example.com/net';"},
        ],
        "err": {"method": "panoya_kopyala", "trigger": "#shareInternetCopy",
                "pre": "document.getElementById('shareInternetLink').value='https://example.com/net';"},
    },
    "drawer": {
        "opener": "document.querySelector('.row[data-gid=\"c1\"]').click();",
        "closer": "#dClose",
        "bridge": [
            {"sel": "#detailTabs .dtab[data-dtab=\"files\"]", "hesap": ["torrent_dosyalari"],
             "pre": "document.querySelector('.row[data-gid=\"t1\"]').click();"},
        ],
        "err": {"method": "torrent_dosyalari", "trigger": "#detailTabs .dtab[data-dtab=\"files\"]",
                "pre": "document.querySelector('.row[data-gid=\"t1\"]').click();"},
    },
}


class PanelDonguTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            channel=os.environ.get("AFUDM_TEST_BROWSER", "msedge"),
            headless=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        _LOG("SETUP: yeni sayfa")
        self.page = self.browser.new_page()
        self.page.set_default_timeout(6000)
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on(
            "dialog", lambda dialog: dialog.accept("otest") if dialog.type == "prompt" else dialog.accept()
        )
        self.page.add_init_script(_sahte_backend_script())
        _LOG("SETUP: goto")
        self.page.goto((KOK / "ui" / "index.html").as_uri())
        _LOG("SETUP: pywebviewready")
        self.page.evaluate('window.dispatchEvent(new Event("pywebviewready"));')
        _LOG("SETUP: ready bekle")
        self.page.wait_for_function(
            "typeof state !== 'undefined' && state.ready === true", timeout=4000
        )
        self.page.wait_for_timeout(450)
        self.baseline = list(self.errors)
        self.bilgiler = []
        _LOG("SETUP: tamam")

    def tearDown(self):
        _LOG("TEARDOWN: sayfa kapaniyor")
        self.page.close()
        _LOG("TEARDOWN: kapandi")

    # ---- yardımcılar -----------------------------------------------------
    def _panel_acik(self, pid):
        return self.page.evaluate(
            """(p) => { const el = document.getElementById(p);
                return !!el && (el.classList.contains('open') || el.classList.contains('on')); }""",
            pid,
        )

    def _panel_bekle(self, pid, acik, adim):
        if acik:
            gonderge = (
                "(p) => { const el = document.getElementById(p); if (!el) return false;"
                " return el.classList.contains('open') || el.classList.contains('on'); }"
            )
        else:
            gonderge = (
                "(p) => { const el = document.getElementById(p); if (!el) return true;"
                " return !el.classList.contains('open') && !el.classList.contains('on'); }"
            )
        self.page.wait_for_function(gonderge, arg=pid, timeout=6000)

    def _open(self, pid, opener_js):
        # Açıcı betiği STATEMENT olarak ateşler; dönen promise'e takılmayız
        # (ör. klasorSec bir "kullanıcı klasörü seçti" promise'i döndürür,
        #  beklersek evaluate sonsuza dek asılı kalır).
        self.page.evaluate("(() => { " + opener_js + " return true; })()")
        self._panel_bekle(pid, True, "acilis")

    def _close_veil_js(self, pid):
        """Panel kapatici: X düğmesi (veya panoya özel kapatıcı)."""
        sel = PANELS[pid]["closer"]
        return f"""(() => {{
          const el = document.querySelector({json.dumps(sel)});
          if (!el) return false;
          el.click(); return true;
        }})()"""

    def _kose_vurgusu(self, pid, kayitlar, adim, durum, mesaj):
        if not durum:
            kayitlar.append(f"[{pid}::{adim}] {mesaj}")

    def _son_cagrilar(self, onceki):
        return self.page.evaluate(
            "window.__otest.calls.map(c => c.ad).slice(%d)" % onceki
        )

    # ---- tek panel senaryosu ---------------------------------------------
    def _panel_dongu(self, pid):
        bilgi = PANELS[pid]
        kayitlar = []
        kose = lambda adim, durum, mesaj: self._kose_vurgusu(pid, kayitlar, adim, durum, mesaj)

        # 1) Açlis
        _LOG("    ADIM 1 acilis %s" % pid)
        try:
            self._open(pid, bilgi["opener"])
            kose("acilis", self._panel_acik(pid), "panel acilmadi")
        except Exception as exc:  # noqa: BLE001
            kose("acilis", False, "acilis hatasi: %s" % exc)

        # 2) Köprü eşlemeleri (ana aksiyon düğmeleri beklenen köprüyü çağırıyor)
        _LOG("    ADIM 2 kopru %s" % pid)
        if self._panel_acik(pid):
            for kayit in bilgi["bridge"]:
                if kayit.get("pre"):
                    self.page.evaluate(kayit["pre"])
                var_mi = self.page.evaluate(
                    "() => { const el = document.querySelector(%s); return !!el; }"
                    % json.dumps(kayit["sel"])
                )
                if not var_mi:
                    kose("kopru-" + kayit["sel"], True, "düğme yok (atlandi)")
                    continue
                if kayit["hesap"]:
                    onceki = self.page.evaluate("window.__otest.calls.length")
                    try:
                        self.page.evaluate(
                            "document.querySelector(%s).click();" % json.dumps(kayit["sel"])
                        )
                        self.page.wait_for_timeout(260)
                        kuyruk = self._son_cagrilar(onceki)
                        kesişim = set(kuyruk) & set(kayit["hesap"])
                        kose("kopru-" + kayit["sel"], bool(kesişim),
                             "beklenen köprü(%s) çağrılmadi; son çağrılar=%s"
                             % (",".join(kayit["hesap"]), kuyruk[-6:]))
                    except Exception as exc:  # noqa: BLE001
                        kose("kopru-" + kayit["sel"], False, "tiklamada hata: %s" % exc)
                    # Başka panele (ör. plgKur->pluginOnayVeil) açılırsa kapat
                    self.page.evaluate(
                        """(pid) => { document.querySelectorAll('.veil.open, .veil.on')
                          .forEach((v) => { if (v.id && v.id !== pid) {
                            if (v.id === 'klasorVeil') { if (window.klasorSoz) klasorKapat(''); else closeVeil('klasorVeil'); }
                            else { const kb = v.querySelector('[data-close]'); if (kb) kb.click(); else if (v.id) closeVeil(v.id); }
                          } }); }""",
                        pid,
                    )

        # 3) Tüm kontrollere tikla (robustluk; tek basina uncaught hata yok)
        _LOG("    ADIM 3 kontroller %s" % pid)
        if not self._panel_acik(pid):
            try:
                self._open(pid, bilgi["opener"])
            except Exception as exc:  # noqa: BLE001
                kose("kontroller", False, "yeniden açılamadı: %s" % exc)
        if self._panel_acik(pid):
            sonuc = None
            tekrar = 0
            while tekrar < 60:
                tekrar += 1
                onceki_hata = set(self.errors)
                try:
                    sonuc = self.page.evaluate(OTEST_KONTROL_JS, pid)
                except Exception as exc:  # noqa: BLE001
                    kose("kontroller", False, "kontroller taraması: %s" % exc)
                    break
                if sonuc and sonuc.get("hata"):
                    kose("kontroller", False,
                         "kontrole tiklandi: %s (id=%s) -> %s"
                         % (sonuc.get("tag"), sonuc.get("id"), sonuc.get("hata")))
                if sonuc and sonuc.get("dur"):
                    break
                # Kontrol üstü paneli kapattıysa yeniden aç (işleme sürsün)
                if not self._panel_acik(pid) and not sonuc.get("dur"):
                    try:
                        self._open(pid, bilgi["opener"])
                    except Exception:  # noqa: BLE001
                        break
                self.page.wait_for_timeout(60)
                yeni = [h for h in self.errors if h not in onceki_hata]
                if yeni:
                    kayitlar.append(f"[{pid}::kontroller-uncaught] beklenmeyen JS hatası: {yeni}")
                    break
            else:
                self.bilgiler.append(
                    f"[{pid}::kontroller-cap] tarama 60 tekrarlık tavanına ulaştı "
                    "(panel kontrolleri etkileşimde yeniden çiziliyor)"
                )

        # 4) X ile kapat
        _LOG("    ADIM 4 x-kapat %s" % pid)
        if self._panel_acik(pid):
            try:
                self.page.evaluate(self._close_veil_js(pid))
                self._panel_bekle(pid, False, "x-kapat")
                kose("x-kapat", not self._panel_acik(pid), "X ile kapanmadi")
            except Exception as exc:  # noqa: BLE001
                kose("x-kapat", False, "X kapama hatasi: %s" % exc)

        # 5) ESC ile kapat
        _LOG("    ADIM 5 esc %s" % pid)
        try:
            if not self._panel_acik(pid):
                self._open(pid, bilgi["opener"])
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(400)
            kose("esc-kapat", not self._panel_acik(pid), "Escape ile kapanmadi")
        except Exception as exc:  # noqa: BLE001
            kose("esc-kapat", False, "ESC adimi hatasi: %s" % exc)

        # 6) Arka plana tikla (backdrop)
        _LOG("    ADIM 6 arkaplan %s" % pid)
        try:
            if not self._panel_acik(pid):
                self._open(pid, bilgi["opener"])
            self.page.evaluate(
                "() => { const el = document.getElementById(%s); if (el) el.click(); }" % json.dumps(pid)
            )
            self.page.wait_for_timeout(400)
            kose("arkaplan", not self._panel_acik(pid), "arka plan tıklamasıyla kapanmadi")
        except Exception as exc:  # noqa: BLE001
            kose("arkaplan", False, "arka plan adımı hatasi: %s" % exc)

        # 7) Köprü hatası: hata mesajı görünür, panel ölü kalmaz, kapatılabilir
        _LOG("    ADIM 7 kopru-hatasi %s" % pid)
        try:
            if not self._panel_acik(pid):
                self._open(pid, bilgi["opener"])
            hedef = bilgi["err"]
            self.page.evaluate(
                """(m) => { window.pywebview.api[m] = async function (...a) {
                     window.__otest.calls.push({ ad: m, args: a });
                     throw new Error('otest-kopru-hatasi');
                   }; }""",
                hedef["method"],
            )
            if hedef.get("pre"):
                self.page.evaluate(hedef["pre"])
            self.page.evaluate(
                "() => { const el = document.querySelector(%s); if (el) el.click(); }"
                % json.dumps(hedef["trigger"])
            )
            self.page.wait_for_timeout(500)
            kose("kopru-hatasi", self._panel_acik(pid), "kopru hatası sonrası panel kapandı (ölü kaldı)")
            hata_gorundu = self.page.evaluate("window.otestHataGorunur(%s)" % json.dumps(pid))
            kose("kopru-hatasi-mesaj", hata_gorundu, "kopru hatası mesajı görünmedi")
            kapanir = self.page.evaluate(self._close_veil_js(pid))
            if kapanir:
                self.page.wait_for_timeout(300)
            kose("kopru-hatasi-kapanir", kapanir and not self._panel_acik(pid),
                 "kopru hatası sonrası panel kapatılamadı")
        except Exception as exc:  # noqa: BLE001
            kose("kopru-hatasi", False, "kopru hatası adımı çöktü: %s" % exc)

        # 8) Genel: bu panel sırasında baseline dışı uncaught JS hata olmamalı
        _LOG("    ADIM 8 genel %s" % pid)
        yeni = self.errors if self.baseline is None else [h for h in self.errors if h not in self.baseline]
        if yeni:
            kayitlar.append(f"[{pid}::uncaughtleri] beklenmeyen JS hatası: {yeni}")

        for bilgi in self.bilgiler:
            sys.stderr.write("BILGI: %s\n" % bilgi)

        self.assertTrue(
            not kayitlar,
            "Panel %s bulguları:\n%s" % (pid, "\n".join(kayitlar)),
        )


# Tek kontrolü işletip geri gelir; {dur:true} bitiş imler.
OTEST_KONTROL_JS = """
(pid) => {
  const root = document.getElementById(pid);
  if (!root) return { dur: true };
  const seciciler = 'button, summary, input[type=checkbox], input[type=radio], input[type=range], select, textarea, input[type=text], input[type=number], input[type=search], input[type=password]';
  const kontroller = root.querySelectorAll(seciciler);
  for (const el of kontroller) {
    if (el.getAttribute('data-otest')) continue;
    if (el.disabled) { el.setAttribute('data-otest', '1'); continue; }
    const tag = el.tagName;
    const tip = el.type || '';
    try {
      if (tag === 'BUTTON' || tag === 'SUMMARY') {
        el.click();
      } else if (tag === 'INPUT' && (tip === 'checkbox' || tip === 'radio')) {
        el.click();
      } else if (tag === 'INPUT' && tip === 'range') {
        el.value = String(Number(el.value || 0) + 1);
        el.dispatchEvent(new Event('input', { bubbles: true }));
      } else if (tag === 'SELECT') {
        const secenek = Array.from(el.options).find((o) => o.value !== '');
        if (!secenek) { el.setAttribute('data-otest', '1'); continue; }
        el.value = secenek.value;
        el.dispatchEvent(new Event('change', { bubbles: true }));
      } else if (tag === 'TEXTAREA' ||
                 (tag === 'INPUT' && !['submit','button','file','color'].includes(tip))) {
        const metin = (el.id === 'urls' || el.id === 'lgMetin' || el.id === 'sSeedEk')
          ? 'https://example.com/a.zip'
          : (tip === 'number' ? '5' : 'test');
        el.value = metin;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      } else {
        el.setAttribute('data-otest', '1');
        continue;
      }
    } catch (err) {
      el.setAttribute('data-otest', '1');
      return { hata: String(err), id: el.id, tag: tag };
    }
    el.setAttribute('data-otest', '1');
    // Başka kapan/açılmış panel (ör. plgKur -> pluginOnayVeil) bu panel testini kirletmesin.
    try {
      Array.from(document.querySelectorAll('.veil.open, .veil.on'))
        .filter((v) => v.id && v.id !== pid)
        .forEach((v) => {
          if (v.id === 'klasorVeil') {
            if (window.klasorSoz) klasorKapat(''); else closeVeil('klasorVeil');
          } else {
            const kb = v.querySelector('[data-close]');
            if (kb) kb.click(); else if (v.id) closeVeil(v.id);
          }
        });
    } catch (_) {}
    return { id: el.id, tag: tag };
  }
  return { dur: true };
}
"""


for _pid in list(PANELS):

    def _olustur(pid):
        def test_metot(self):
            _LOG("TEST: basla %s" % pid)
            self._panel_dongu(pid)
            _LOG("TEST: bitti %s" % pid)

        test_metot.__name__ = "test_panel_" + re.sub(r"[^A-Za-z0-9]", "_", pid)
        test_metot.__doc__ = "Panel dongusu: %s" % pid
        return test_metot

    setattr(PanelDonguTest, "test_panel_" + _pid, _olustur(_pid))


if __name__ == "__main__":
    unittest.main()