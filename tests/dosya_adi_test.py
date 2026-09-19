"""tests/dosya_adi_test.py — RFC 6266, RFC 5987, MIME uzantisi ve dosya guvenligi testleri.
dlman v1.12.0 karsilastirmali tum gereksinimleri ag gerektirmeden kontrol eder.
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from core import dosya_adi


def test_content_disposition():
    print("1) Content-Disposition baslik ayrıştırması")
    # Duz tirnaksiz
    res = dosya_adi.filename_from_content_disposition("attachment; filename=afudm-main.zip")
    assert res == "afudm-main.zip", f"Beklenen afudm-main.zip, alinan {res}"
    print("  [GECTI] tirnaksiz dosya adi")

    # Duz tirnakli
    res = dosya_adi.filename_from_content_disposition('attachment; filename="rapor 2026.pdf"')
    assert res == "rapor 2026.pdf", f"Beklenen rapor 2026.pdf, alinan {res}"
    print("  [GECTI] tirnakli ve bosluklu dosya adi")

    # Tirnak icinde noktalı virgül
    res = dosya_adi.filename_from_content_disposition('attachment; filename="a;b.zip"; size=42')
    assert res == "a;b.zip", f"Beklenen a;b.zip, alinan {res}"
    print("  [GECTI] tirnak icinde noktali virgul")

    # RFC 5987 extended form (filename*) - Turkce karakterli
    hdr = "attachment; filename=\"yedek.zip\"; filename*=UTF-8''t%C3%BCrk%C3%A7e%20dosya.zip"
    res = dosya_adi.filename_from_content_disposition(hdr)
    assert res == "türkçe dosya.zip", f"Beklenen türkçe dosya.zip, alinan {res}"
    print("  [GECTI] RFC 5987 filename* uzantisi (UTF-8)")

    # filename* her zaman filename'i ezer
    hdr2 = "attachment; filename=\"fallback.zip\"; filename*=UTF-8''as%C4%B1l.zip"
    assert dosya_adi.filename_from_content_disposition(hdr2) == "asıl.zip"
    print("  [GECTI] filename* filename'e ustun gelir")

    # Buyuk/kucuk harf duyarsiz baslik
    hdr3 = "ATTACHMENT; FileName=\"Setup.exe\""
    assert dosya_adi.filename_from_content_disposition(hdr3) == "Setup.exe"
    print("  [GECTI] buyuk/kucuk harf duyarsizligi")

    # Sadece attachment (dosya adi yok)
    assert dosya_adi.filename_from_content_disposition("attachment") is None
    assert dosya_adi.filename_from_content_disposition("inline") is None
    print("  [GECTI] dosya adsiz baslik None dondurur")


def test_split_stem_ext():
    print("2) Akilli kok / uzanti ayrıştırması (split_stem_ext)")
    # Normal dosya
    assert dosya_adi.split_stem_ext("arsiv.zip") == ("arsiv", "zip")
    assert dosya_adi.split_stem_ext("video.tar.gz") == ("video.tar", "gz")
    print("  [GECTI] standart uzantilar ayrildi")

    # Surum numaralari uzanti ZANNEDILMEZ (dlman'deki regression onleme kurali)
    assert dosya_adi.split_stem_ext("afudm-v1.12.0") == ("afudm-v1.12.0", None)
    assert dosya_adi.split_stem_ext("paket.001") == ("paket.001", None)
    print("  [GECTI] surum numaralari (.0, .001) uzanti sayilmadi")

    # Gizli dosyalar
    assert dosya_adi.split_stem_ext(".gitignore") == (".gitignore", None)
    print("  [GECTI] gizli dosyalar (.gitignore) korundu")

    # Asiri uzun uzantilar
    assert dosya_adi.split_stem_ext("dosya.cokuzunbiruzanti") == ("dosya.cokuzunbiruzanti", None)
    print("  [GECTI] sahte uzun uzanti ayiklandi")


def test_ensure_extension():
    print("3) MIME turunden uzanti tamamlama (ensure_extension)")
    # Uzantisiz ad MIME ile tamamlanir
    assert dosya_adi.ensure_extension("main", "application/zip") == "main.zip"
    assert dosya_adi.ensure_extension("kurulum", "application/x-msdownload") == "kurulum.exe"
    assert dosya_adi.ensure_extension("belge", "application/pdf") == "belge.pdf"
    assert dosya_adi.ensure_extension("sayfa", "text/html; charset=utf-8") == "sayfa.html"
    print("  [GECTI] MIME'dan dogru uzantilar eklendi")

    # Zaten uzantisi olan dosya degismez
    assert dosya_adi.ensure_extension("zaten.zip", "application/pdf") == "zaten.zip"
    print("  [GECTI] mevcut uzanti ezilmedi")

    # octet-stream tahmin yapmaz
    assert dosya_adi.ensure_extension("belirsiz", "application/octet-stream") == "belirsiz"
    assert dosya_adi.ensure_extension("belirsiz", None) == "belirsiz"
    print("  [GECTI] application/octet-stream rastgele tahmin yapmaz")


def test_guvenli_dosya_adi():
    print("4) Guvenli dosya adi ve sanitizasyon")
    # Dizin atlama saldirilari yol ayraclari temizlenerek etkisizlestirilir
    assert dosya_adi.guvenli_dosya_adi("../../etc/passwd") == ".._.._etc_passwd"
    assert dosya_adi.guvenli_dosya_adi(r"..\..\windows\system32\evil.dll") == ".._.._windows_system32_evil.dll"
    print("  [GECTI] path traversal (../../) ayrac temizligiyle etkisizlestirildi")
    # Yasakli karakterler
    assert dosya_adi.guvenli_dosya_adi("gecer:siz|ad?.txt") == "gecer_siz_ad_.txt"
    print("  [GECTI] yasakli karakterler '_' oldu")

    # Sondaki nokta ve bosluklar (Windows dosya sistemi kabul etmez)
    assert dosya_adi.guvenli_dosya_adi("rapor.pdf .  ") == "rapor.pdf"
    print("  [GECTI] sondaki nokta ve bosluklar temizlendi")

    # Windows DOS ayrilmis aygit adlari (CON, NUL, PRN vb.)
    assert dosya_adi.guvenli_dosya_adi("NUL") == "_NUL"
    assert dosya_adi.guvenli_dosya_adi("nul.txt") == "_nul.txt"
    assert dosya_adi.guvenli_dosya_adi("com1") == "_com1"
    assert dosya_adi.guvenli_dosya_adi("normal.txt") == "normal.txt"
    print("  [GECTI] Windows DOS aygit adlari (_NUL, _nul.txt) guvene alindi")

    # Uzun isimler uzantisi korunarak kirpilir
    uzun = "a" * 300 + ".zip"
    temiz_uzun = dosya_adi.guvenli_dosya_adi(uzun)
    assert len(temiz_uzun) <= dosya_adi.EN_FAZLA_KARAKTER
    assert temiz_uzun.endswith(".zip")
    print("  [GECTI] asiri uzun ad uzanti korunarak kirpildi")


def test_resolve_filename():
    print("5) Uctan uca dosya adi cozumleme (resolve_filename)")
    # Content-Disposition URL yolundan ustundur (codeload GitHub ornegi)
    url = "https://codeload.github.com/novincode/dlman/zip/refs/heads/main"
    cd = "attachment; filename=dlman-main.zip"
    ct = "application/zip"
    assert dosya_adi.resolve_filename(url, cd, ct) == "dlman-main.zip"
    print("  [GECTI] Content-Disposition URL yolunu yendi")

    # CD yoksa ama MIME varsa
    url2 = "https://example.com/get/9N7JSXC1SJK6"
    assert dosya_adi.resolve_filename(url2, None, "application/x-msdownload") == "9N7JSXC1SJK6.exe"
    print("  [GECTI] CD yokken MIME ile uzanti bulundu")

    # URL'den yuzde kodlu dosya adi
    url3 = "https://example.com/files/Proje%20Raporu.pdf"
    assert dosya_adi.resolve_filename(url3) == "Proje Raporu.pdf"
    print("  [GECTI] URL'deki %20 gibi karakterler cozuldu")

    # Parametreli URL
    url4 = "https://example.com/download.php?file=setup.exe&token=xyz"
    assert dosya_adi.resolve_filename(url4) == "download.php"
    print("  [GECTI] query string dosya adina karismadi")

    # Magnet linki
    magnet = "magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10&dn=Sintel.mp4"
    assert dosya_adi.resolve_filename(magnet) == "Sintel.mp4"
    print("  [GECTI] magnet dn adi alindi")


def main():
    test_content_disposition()
    test_split_stem_ext()
    test_ensure_extension()
    test_guvenli_dosya_adi()
    test_resolve_filename()
    print("\nTum dosya adi ve RFC testleri basariyla GECTI!")


if __name__ == "__main__":
    main()
