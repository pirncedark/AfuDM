"""Ozel baslik cubugu testi — ACIK AfuDM penceresinde, FARE KULLANMADAN.

ONKOSUL: AfuDM acik (yeni kodla). core/pencere.py Windows basligini kaldirir,
WebView2 CSS `app-region: drag` alanini gercek baslik gibi bildirir.

Windows'un WindowFromPoint kurali AfuDM agacinda taklit edilir.

Her seviyede alt pencereler z sirasiyla gezilir: gorunur + dikdortgen + sekil
bolgesi noktayi iceriyorsa WM_NCHITTEST sorulur; HTTRANSPARENT ise kardese
gecilir, degilse icine inilir. Son pencerenin yaniti Windows'un karari olur.
"""
import ctypes
import sys
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
HT = {-1: "TRANSPARENT", 0: "NOWHERE", 1: "CLIENT", 2: "CAPTION", 10: "LEFT", 11: "RIGHT",
      12: "TOP", 13: "TOPLEFT", 14: "TOPRIGHT", 15: "BOTTOM", 17: "BOTTOMRIGHT"}

fails: list[str] = []


def check(ad: str, kosul: bool, ayrinti: str = "") -> None:
    print(("  [GECTI] " if kosul else "  [BASARISIZ] ") + ad + (f" — {ayrinti}" if ayrinti else ""))
    if not kosul:
        fails.append(ad)


bulunan = []


@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def gez(hwnd, _):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    if user32.IsWindowVisible(hwnd) and "AfuDM" in buf.value:
        bulunan.append(hwnd)
    return True


user32.EnumWindows(gez, 0)
if not bulunan:
    print("AfuDM penceresi yok — once uygulamayi ac.")
    sys.exit(2)
ana = bulunan[0]
kok = wintypes.RECT(); user32.GetWindowRect(ana, ctypes.byref(kok))
ist = wintypes.POINT(0, 0); user32.ClientToScreen(ana, ctypes.byref(ist))
cr = wintypes.RECT(); user32.GetClientRect(ana, ctypes.byref(cr))


def noktada(h, sx, sy):
    if not user32.IsWindowVisible(h):
        return False
    r = wintypes.RECT(); user32.GetWindowRect(h, ctypes.byref(r))
    if not (r.left <= sx < r.right and r.top <= sy < r.bottom):
        return False
    rgn = gdi32.CreateRectRgn(0, 0, 0, 0)
    try:
        if user32.GetWindowRgn(h, rgn) > 1:
            return bool(gdi32.PtInRegion(rgn, sx - r.left, sy - r.top))
        return True
    finally:
        gdi32.DeleteObject(rgn)


def karar(sx, sy):
    lp = ((sy & 0xFFFF) << 16) | (sx & 0xFFFF)
    h = ana
    sonuc = user32.SendMessageW(h, 0x84, 0, lp)
    if sonuc != 1:
        return sonuc, "ana"
    while True:
        cocuk = user32.GetWindow(h, 5)  # GW_CHILD (en ustteki)
        secilen = None
        while cocuk:
            if noktada(cocuk, sx, sy):
                v = user32.SendMessageW(cocuk, 0x84, 0, lp)
                if v != -1:
                    secilen, sonuc = cocuk, v
                    break
            cocuk = user32.GetWindow(cocuk, 2)  # GW_HWNDNEXT
        if not secilen:
            s = ctypes.create_unicode_buffer(64); user32.GetClassNameW(h, s, 64)
            return sonuc, s.value
        h = secilen


def ht(x, y):
    return karar(ist.x + x, ist.y + y)[0]


gen = cr.right
check("Windows basligi YOK (istemci pencerenin ustunden basliyor)", ist.y == kok.top,
      f"istemci ustu {ist.y}, pencere ustu {kok.top}")
check("bant izinin bos alani surukleme alani (CAPTION)", ht(500, 40) == 2, HT.get(ht(500, 40)))
check("hiz rakami da surukleme alani", ht(60, 40) == 2)
for ad, x in (("kapat", gen - 23), ("buyut", gen - 69), ("kucult", gen - 115)):
    check(f"{ad} dugmesi tiklanabilir (CLIENT)", ht(x, 16) == 1, HT.get(ht(x, 16)))
check("motor rozeti tiklanabilir", ht(gen - 230, 26) == 1)
check("ust kenar seridi sayfada (JS boyutlandirir)", ht(500, 1) == 1)
check("arac cubugu ve liste suruklenmez", ht(300, 137) == 1 and ht(600, 400) == 1)
check("sol kenardan yerel boyutlandirma", karar(ist.x - 5, ist.y + 300)[0] == 10)
check("alt kenardan yerel boyutlandirma", karar(ist.x + 500, ist.y + cr.bottom + 4)[0] == 15)

print("\n" + ("Hepsi gecti" if not fails else "BASARISIZ: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
