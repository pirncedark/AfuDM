"""Rust UI and extension translation contracts; no desktop Python imports."""
import json
import re
from pathlib import Path
KOK = Path(__file__).resolve().parents[1]

def kontrol(ad, sart, ek=""):
    assert sart, f"{ad}: {ek}"

def test_extension_locales():
    loc_tr = json.loads((KOK / "extension/_locales/tr/messages.json").read_text(encoding="utf-8"))
    loc_en = json.loads((KOK / "extension/_locales/en/messages.json").read_text(encoding="utf-8"))
    kontrol("uzanti tr/en anahtarlari ayni", set(loc_tr) == set(loc_en),
            ", ".join(sorted(set(loc_tr) ^ set(loc_en)))[:60])
    man = json.loads((KOK / "extension/manifest.json").read_text(encoding="utf-8"))
    msg_anahtar = set(re.findall(r"__MSG_([A-Za-z0-9_]+)__", json.dumps(man)))
    kontrol("manifest __MSG__ kullaniyor", len(msg_anahtar) >= 3, ", ".join(sorted(msg_anahtar)))
    yok = sorted(k for k in msg_anahtar if k not in loc_tr)
    kontrol("manifest'teki her __MSG__ sozlukte var", not yok, ", ".join(yok))
    kontrol("default_locale ayarli", man.get("default_locale") == "tr", str(man.get("default_locale")))

    js_anahtar = set()
    for ad in ("extension/popup.js", "extension/background.js"):
        js_anahtar |= set(re.findall(r'chrome\.i18n\.getMessage\(\s*"([A-Za-z0-9_]+)"',
                                     (KOK / ad).read_text(encoding="utf-8")))
    # content.js getMessage'i t() ardina gizler; taranmadigi icin eksik anahtar
    # kullanicinin ekraninda HAM ANAHTAR ADI olarak gorunurdu (t() oyle duser).
    js_anahtar |= set(re.findall(r't\(\s*"([A-Za-z0-9_]+)"',
                                 (KOK / "extension/content.js").read_text(encoding="utf-8")))
    kontrol("uzanti JS'i getMessage kullaniyor", len(js_anahtar) > 5, f"{len(js_anahtar)} anahtar")
    yok = sorted(k for k in js_anahtar if k not in loc_tr)
    kontrol("uzanti JS'indeki her anahtar sozlukte var", not yok, ", ".join(yok[:5]))

    # Bos sonucun sebebi anahtar ADI olarak dondurulur (background.js -> content.js
    # t(yanit.reason)). getMessage("...") taramasi bunlari GORMEZ; ayrica yoklanir.
    bg = (KOK / "extension/background.js").read_text(encoding="utf-8")
    sebep = set(re.findall(r'return "(vpNone[A-Za-z0-9_]*)"', bg))
    kontrol("bos sonuc sebepleri uretiliyor", len(sebep) >= 4, f"{len(sebep)} sebep")
    yok = sorted(k for k in sebep if k not in loc_tr)
    kontrol("her sebep anahtari sozlukte var", not yok, ", ".join(yok))
    kontrol("content.js sebebi kullaniyor",
            "yanit.reason" in (KOK / "extension/content.js").read_text(encoding="utf-8"))


def blok_ayikla(metin: str, baslangic: str) -> str:
    """`tr: {` gibi bir baslangictan sonraki dengeli suslu parantez blogunu dondurur."""
    i = metin.index(baslangic) + len(baslangic) - 1
    derinlik = 0
    for j in range(i, len(metin)):
        if metin[j] == "{":
            derinlik += 1
        elif metin[j] == "}":
            derinlik -= 1
            if derinlik == 0:
                return metin[i:j + 1]
    raise ValueError("kapanmayan blok: " + baslangic)


# Anahtarlarda TIRE de olabilir ("eng.yt-dlp"); karakter kumesinde unutmak
# var olan anahtari "eksik" gosteriyordu.
ANAHTAR_RE = re.compile(r'"([A-Za-z0-9_.\-]+)"\s*:\s*"((?:[^"\\]|\\.)*)"')


def sozluk(blok: str) -> dict:
    return {m.group(1): m.group(2) for m in ANAHTAR_RE.finditer(blok)}


def test_rust_ui_locales():
    print("1) ui/i18n.js sozlugu")
    js = (KOK / "rs" / "app" / "ui" / "i18n.js").read_text(encoding="utf-8")
    tr = sozluk(blok_ayikla(js, "  tr: {"))
    en = sozluk(blok_ayikla(js, "  en: {"))
    kontrol("tr sozlugu dolu", len(tr) > 40, f"{len(tr)} anahtar")
    eksik_en = sorted(set(tr) - set(en))
    eksik_tr = sorted(set(en) - set(tr))
    kontrol("en'de eksik anahtar yok", not eksik_en, ", ".join(eksik_en[:5]))
    kontrol("tr'de eksik anahtar yok", not eksik_tr, ", ".join(eksik_tr[:5]))
    bos = [k for k, v in list(tr.items()) + list(en.items()) if not v.strip()]
    kontrol("bos metin yok", not bos, ", ".join(bos[:5]))

    print("2) index.html anahtarlari")
    html = (KOK / "rs" / "app" / "ui" / "index.html").read_text(encoding="utf-8")
    html_anahtar = set(re.findall(r'data-i18n(?:-ph|-title|-html)?="([^"]+)"', html))
    kontrol("index.html anahtar kullaniyor", len(html_anahtar) > 30, f"{len(html_anahtar)} anahtar")
    yok = sorted(k for k in html_anahtar if k not in tr)
    kontrol("index.html'deki her anahtar sozlukte var", not yok, ", ".join(yok[:5]))

    print("3) app.js anahtarlari")
    app = (KOK / "rs" / "app" / "ui" / "app.js").read_text(encoding="utf-8")
    # Yalniz SABIT anahtarlar: t("x") veya t("x", {...}). Dinamik kurulan
    # t("state." + status) bilerek disarida — ailesi hemen asagida denetleniyor.
    app_anahtar = set(re.findall(r'\bt\(\s*"([A-Za-z0-9_.\-]+)"\s*[),]', app))
    kontrol("app.js anahtar kullaniyor", len(app_anahtar) > 20, f"{len(app_anahtar)} anahtar")
    yok = sorted(k for k in app_anahtar if k not in tr)
    kontrol("app.js'teki her anahtar sozlukte var", not yok, ", ".join(yok[:5]))

    # Dinamik aile: aria2/yt-dlp'nin dondurebilecegi HER durum icin karsilik olmali
    DURUMLAR = ("active", "waiting", "paused", "complete", "error", "removed",
                "scheduled", "queued", "seeding")
    yok = sorted("state." + d for d in DURUMLAR if "state." + d not in tr)
    kontrol("her indirme durumu icin metin var", not yok, ", ".join(yok))

    # Motor aciklamalari da dinamik cagriliyor: t("eng." + ad)
    engine_source = (KOK / "rs/crates/afudm-engine/src/engines.rs").read_text(encoding="utf-8")
    engine_names = re.findall(r'Motor \{ ad:\s*"([^"]+)"', engine_source)
    kontrol("Rust motor envanteri dolu", len(engine_names) >= 4)

    yok = sorted("eng." + a for a in engine_names if "eng." + a not in tr)
    kontrol("her motor icin aciklama var", not yok, ", ".join(yok))
    yok_en = sorted("eng." + a for a in engine_names if "eng." + a not in en)
    kontrol("motor aciklamalari Ingilizce de var", not yok_en, ", ".join(yok_en))
    kontrol("app.js i18n.js'i yukluyor", 'src="i18n.js"' in html)
    kontrol("i18n.js app.js'ten ONCE yukleniyor", html.index('src="i18n.js"') < html.index('src="app.js"'))

    print("6) mobil ve paylasim bildirimleri")
    gerekli = ("share.downloadingToPhone", "mobile.torrentTitle", "mobile.loading",
               "mobile.filesNotReady", "mobile.filesNotFound", "mobile.filesLoadFailed")
    kontrol("mobil metinleri tr/en sozluklerinde var",
            all(k in tr and k in en for k in gerekli),
            ", ".join(k for k in gerekli if k not in tr or k not in en))
    app = (KOK / "rs/app/ui/app.js").read_text(encoding="utf-8")
    mobile = (KOK / "rs/app/ui/mobil.html").read_text(encoding="utf-8")
    kontrol("telefon bildirimi i18n anahtarini kullaniyor", 't("share.downloadingToPhone")' in app)
    kontrol("mobil sayfa i18n sozlugunu yukluyor", '<script src="i18n.js"></script>' in mobile)
    kontrol("mobil torrent metinleri i18n anahtarlarini kullaniyor",
            all(f't("{k}")' in mobile for k in gerekli[1:]))
