"""Ozel baslik cubugu — Windows'un gri baslik seridi yerine uygulamanin kendi ustu.

Neden pywebview'in `frameless=True`'su degil: Windows'ta cercevesiz pencere
kenardan BOYUTLANMAZ, surukleme JS ile fare izlenerek yapilir (takilir, Snap
calismaz). Burada pencere NORMAL (boyutlanabilir) kalir; yalniz baslik alani
istemci alanina katilir:

  1. WM_NCCALCSIZE alt sinifi: ust kenar varsayilan hesaptan GERI alinir, yani
     baslik yuksekligi kadar alan uygulamaya verilir. Sol/sag/alt kenarlar
     Windows 10/11'de gorunmez boyutlandirma kenari olarak KALIR; golge, yuvarlak
     kose, Snap ve gorev cubugu adi bozulmaz.
  2. WebView2 `IsNonClientRegionSupportEnabled`: CSS `app-region: drag` olan
     alan Windows'un GERCEK basligi gibi davranir (surukle, Snap, cift tikla
     buyut, sag tikla sistem menusu).
  3. Ust kenardan boyutlandirma: baslik alani artik sayfanin icinde oldugu icin
     ince bir serit fareye basilinca pencereye WM_NCLBUTTONDOWN(HTTOP) gonderir;
     Windows kendi boyutlandirma dongusunu baslatir.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

WM_NCCALCSIZE = 0x0083
WM_NCLBUTTONDOWN = 0x00A1
VK_LBUTTON = 0x01
HT_KENAR = {"top": 12, "topleft": 13, "topright": 14}
SWP_BICIM_DEGISTI = 0x0020 | 0x0001 | 0x0002 | 0x0004 | 0x0010  # FRAMECHANGED|NOSIZE|NOMOVE|NOZORDER|NOACTIVATE
SM_CYSIZEFRAME = 33
SM_CXPADDEDBORDER = 92

_ETKIN = sys.platform == "win32"
if _ETKIN:
    user32 = ctypes.windll.user32
    comctl32 = ctypes.windll.comctl32
    LRESULT = ctypes.c_ssize_t
    ALTSINIF = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                  wintypes.LPARAM, ctypes.c_size_t, ctypes.c_size_t)
    comctl32.DefSubclassProc.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    comctl32.DefSubclassProc.restype = LRESULT
    comctl32.SetWindowSubclass.argtypes = [wintypes.HWND, ALTSINIF, ctypes.c_size_t, ctypes.c_size_t]
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = LRESULT
    user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, wintypes.UINT]
    user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]

_alt_sinif_ref = None  # ctypes geri cagrisi cop toplanmasin


def _kenar_kalinligi(hwnd) -> int:
    dpi = user32.GetDpiForWindow(hwnd) or 96
    return (user32.GetSystemMetricsForDpi(SM_CYSIZEFRAME, dpi)
            + user32.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi))


def webview2_hazirligini_yama() -> None:
    """CSS app-region destegi + KOPYALA/YAPISTIR kisayollari.

    Ayar gezinme basladiktan sonra verilirse bir SONRAKI gezinmeye kadar
    etkisizdir; bu yuzden pywebview'in hazir olay isleyicisinin basina eklenir.

    KOPYALA/YAPISTIR: pywebview `AreBrowserAcceleratorKeysEnabled` degerini
    DEBUG bayragina bagliyor (webview/platforms/edgechromium.py), yani surumde
    Ctrl+C / Ctrl+V / Ctrl+X / Ctrl+A HIC calismiyordu — kullanicinin
    bildirdigi kusur bu. Bayragi aciyoruz. Gelistirici araclari AYRI bir ayar
    (`AreDevToolsEnabled`) oldugu icin F12 yine kapali kalir; istenmeyen
    kisayollar (Ctrl+R yeniden yukleme, Ctrl+P yazdirma) arayuz tarafinda
    engellenir (ui/app.js).
    """
    if not _ETKIN:
        return
    try:
        from webview.platforms import edgechromium
    except Exception:
        return
    asil = edgechromium.EdgeChrome.on_webview_ready
    if getattr(asil, "_afudm", False):
        return

    def hazir(self, sender, args):
        try:
            if args.IsSuccess:
                sender.CoreWebView2.Settings.IsNonClientRegionSupportEnabled = True
        except Exception:
            pass  # eski WebView2: surukleme olmaz ama uygulama calisir
        sonuc = asil(self, sender, args)
        # SIRA ONEMLI: pywebview kendi isleyicisinde bu bayragi debug degerine
        # (yani False'a) YAZIYOR. Once onu calistirip SONRA aciyoruz.
        try:
            if args.IsSuccess:
                sender.CoreWebView2.Settings.AreBrowserAcceleratorKeysEnabled = True
        except Exception:
            pass  # eski WebView2: kisayol yok ama sag tik menusu calisir
        return sonuc

    hazir._afudm = True
    edgechromium.EdgeChrome.on_webview_ready = hazir


def _ui_is_parcaciginda(form, is_):
    """WinForms nesnelerine yalniz olusturuldugu is parcaciginda dokunulur."""
    from System import Action  # pythonnet; pywebview baslamis olmali

    sonuc = []
    form.Invoke(Action(lambda: sonuc.append(is_())))
    return sonuc[0] if sonuc else None


def basligi_kaldir(window) -> bool:
    """Windows basligini istemci alanina kat. `shown` olayindan sonra cagrilir."""
    if not _ETKIN or window.native is None:
        return False
    form = window.native

    def kur():
        hwnd = form.Handle.ToInt64()

        @ALTSINIF
        def alt_sinif(h, mesaj, wp, lp, _kimlik, _veri):
            if mesaj == WM_NCCALCSIZE and wp:
                # lParam -> NCCALCSIZE_PARAMS; ilk RECT yeni istemci alani
                dikdortgen = wintypes.RECT.from_address(lp)
                ust = dikdortgen.top
                sonuc = comctl32.DefSubclassProc(h, mesaj, wp, lp)
                # Buyutulmus pencere ekran disina kenar kalinligi kadar tasar:
                # ust icerik kesilmesin.
                dikdortgen.top = ust + (_kenar_kalinligi(h) if user32.IsZoomed(h) else 0)
                return sonuc
            return comctl32.DefSubclassProc(h, mesaj, wp, lp)

        global _alt_sinif_ref
        _alt_sinif_ref = alt_sinif
        if not comctl32.SetWindowSubclass(hwnd, alt_sinif, 0xAF0D, 0):
            return False
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_BICIM_DEGISTI)
        return True

    return bool(_ui_is_parcaciginda(form, kur))


def one_getir(window) -> None:
    """Tarayicidan indirme geldi: pencere gizli/simge durumundaysa goster ve one al.
    Windows arka plandaki surecin odak calmasini kisitlar; TopMost ac/kapa en
    guvenilir yol (en kotu durumda gorev cubugu yanip soner)."""
    if not _ETKIN or window.native is None:
        return
    form = window.native

    def getir():
        from System.Windows.Forms import FormWindowState
        form.Show()
        if form.WindowState == FormWindowState.Minimized:
            form.WindowState = FormWindowState.Normal
        form.TopMost = True
        form.TopMost = False
        form.Activate()
        return True

    try:
        _ui_is_parcaciginda(form, getir)
    except Exception:
        pass



def kapatinca_gizle(window, etkin_mi, cikiliyor_mi, gizlenince=None) -> bool:
    """Windows X/Alt+F4 olayini qBittorrent gibi tepsiye yonlendir.

    Kucultme olayina dokunulmaz; '-' normal Windows gorev cubuguna iner.
    Tepsi menusu > Cikis gercek kapatmadir ve cikiliyor_mi ile engellenmez.
    """
    if not _ETKIN or window.native is None:
        return False
    form = window.native

    def kur():
        from System.Windows.Forms import FormClosingEventHandler

        def kapanirken(_gonderen, olay):
            try:
                if not cikiliyor_mi() and etkin_mi():
                    olay.Cancel = True
                    form.Hide()
                    if gizlenince:
                        gizlenince()
            except Exception:
                pass

        form.FormClosing += FormClosingEventHandler(kapanirken)
        return True

    try:
        return bool(_ui_is_parcaciginda(form, kur))
    except Exception:
        return False


def kucultunce_gizle(window, etkin_mi, gizlenince=None) -> bool:
    """Kucultme dugmesi pencereyi GOREV CUBUGUNDAN da kaldirsin (tepsiye insin).

    Windows'ta "tepsiye kucult" diye bir pencere bayragi yoktur: pencere simge
    durumuna gecince gizlenir, geri donus tepsi simgesinden olur (bkz. app.py
    build_tray). `etkin_mi` her seferinde OKUNUR, boylece ayar yeniden baslatma
    gerektirmez.
    """
    if not _ETKIN or window.native is None:
        return False
    form = window.native

    def kur():
        from System import EventHandler
        from System.Windows.Forms import FormWindowState

        def boyut_degisti(_gonderen, _olay):
            try:
                if form.WindowState == FormWindowState.Minimized and etkin_mi():
                    form.Hide()
                    if gizlenince:
                        gizlenince()
            except Exception:
                pass

        form.Resize += EventHandler(boyut_degisti)
        return True

    try:
        return bool(_ui_is_parcaciginda(form, kur))
    except Exception:
        return False

def buyutulmus_mu(window) -> bool:
    if not _ETKIN or window.native is None:
        return False
    return bool(user32.IsZoomed(window.native.Handle.ToInt64()))


def kenardan_boyutla(window, kenar: str) -> bool:
    """Ust kenar seridine basildi: Windows'un boyutlandirma dongusunu baslat."""
    kod = HT_KENAR.get(kenar)
    if not _ETKIN or window.native is None or kod is None:
        return False
    # JS -> Python cagrisi eszamansiz; fare birakilmissa dongu "yapiskan"
    # kalir (pencere imleci izler). Dugme hala basili degilse hic baslatma.
    if not user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000:
        return False
    form = window.native

    def basla():
        hwnd = form.Handle.ToInt64()
        user32.ReleaseCapture()
        user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, kod, 0)
        return True

    return bool(_ui_is_parcaciginda(form, basla))
