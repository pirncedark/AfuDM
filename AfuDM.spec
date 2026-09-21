# -*- mode: python ; coding: utf-8 -*-

# Windows version resource (Dosya ozellikleri > Ayrintilar > Surum/telif).
# Imzasiz exe'ler icin "yayinci bilgisi olmayan dosya" gorunumu smart screen
# itibarini dusurur; bu blok en azindan surum/sirket/adres bilgisini exe'ye
# gomer. Surum tek kaynaktan (core/surum.py) cekilir ki etikette kalinti
# surum kalmasin. PyInstaller dahili olarak gelir, ek bagimlilik yok.
import re as _re
from pathlib import Path as _Path

try:
    from core import surum as _surum
except ImportError:
    _surum = None

_SURUM_METIN = "2.4.0"
if _surum is not None:
    try:
        _SURUM_METIN = getattr(_surum, "SURUM", "2.4.0")
    except Exception:
        _SURUM_METIN = "2.4.0"

# "2.4.0" -> (2, 4, 0) ; "-" dev/gunluk derlemelerinde 0'a dus
def _surum_demeti(metin):
    parcalar = _re.findall(r"[0-9]+", metin)[:3]
    while len(parcalar) < 3:
        parcalar.append("0")
    return tuple(int(x) for x in parcalar)

_SR, _SV, _SB = _surum_demeti(_SURUM_METIN)

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

_VERSION_RESOURCE = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(_SR, _SV, _SB, 0),
        prodvers=(_SR, _SV, _SB, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    u"040904B0",
                    [
                        StringStruct(u"CompanyName", u"AfuDM Project"),
                        StringStruct(u"FileDescription", u"AfuDM - indirme yoneticisi"),
                        StringStruct(u"FileVersion", _SURUM_METIN),
                        StringStruct(u"InternalName", u"AfuDM"),
                        StringStruct(u"LegalCopyright", u"(c) AfuDM Project"),
                        StringStruct(u"OriginalFilename", u"AfuDM.exe"),
                        StringStruct(u"ProductName", u"AfuDM"),
                        StringStruct(u"ProductVersion", _SURUM_METIN),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct(u"Translation", [2057, 1200])]),
    ],
)


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['pystray._win32'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Hicbiri import EDILMIYOR; PyInstaller dolayli olarak aliyordu.
        'tkinter', 'numpy', 'matplotlib', 'scipy', 'pandas',
        'cryptography', 'bcrypt', 'nacl', 'OpenSSL', 'paramiko',
        'setuptools', 'pkg_resources', 'pip', 'wheel', 'distutils',
        'unittest', 'doctest', 'pydoc', 'pydoc_data', 'test',
        'xmlrpc', 'lib2to3', 'ensurepip', 'idlelib', 'turtledemo',
        'sqlite3.test', 'curses', 'asyncio',
        # PIL sadece tepsi simgesini cizmek icin; goruntu bicimi eklentileri gereksiz
        'PIL.ImageQt', 'PIL.ImageTk', 'PIL.ImageShow', 'PIL.ImageGrab',
        # DIKKAT: 'PIL.ImageFont' CIKARILAMAZ â€” ImageDraw onu import eder ve
        # tepsi simgesi (pystray + ImageDraw) SESSIZCE kurulmaz; exe'de konsol
        # olmadigi icin aylarca fark edilmedi. OLCULDU 2026-09-18.
        'PIL.ImageCms', 'PIL.ImageFilter', 'PIL.ImageMath',
        'PIL.ImageMorph', 'PIL.ImageOps', 'PIL.ImageStat', 'PIL.ImageWin',
        # pywebview'in istege bagli bagimliliklari â€” arayuzumuz kullanmiyor.
        # DIKKAT: clr / clr_loader / cffi / proxy_tools CIKARILAMAZ; pywebview'in
        # Windows arka ucu (WinForms + WebView2) onlarla ayaga kalkiyor.
        # DIKKAT: 'bottle' de CIKARILAMAZ â€” webview/http.py onu kosulsuz import eder.
        'pygments', 'jinja2', 'mako', 'chardet', 'markupsafe',
        'flask', 'qtpy', 'PyQt5', 'PySide2', 'PySide6', 'gi', 'cefpython3',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AfuDM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX KAPALI â€” bilerek. 16.8 MB'i 13.0 MB'a indiriyordu ama pythonnet'in
    # .NET derlemelerini bozup pywebview JS<->Python koprusunu kopariyordu:
    # pencere aciliyor, arayuz ciziliyor, ama rozet "baglanti yok" diyor ve
    # hicbir dugme calismiyor. 3.8 MB icin uygulamayi islevsiz birakmaya degmez.
    upx=False,
    upx_exclude=[
        # UPX bunlari bozar: .NET yonetimli derlemeler (pywebview WinForms/WebView2
        # koprusu) ve C calisma zamani DLL'leri.
        # .NET YONETIMLI derlemelerin HEPSI: UPX bunlari ya paketleyemiyor ya da
        # paketleyip bozuyor â€” sonucu arayuz is parcaciginin kilitlenmesi oluyor.
        'System.*.dll', 'Microsoft.*.dll', 'Python.Runtime.dll', 'netstandard.dll',
        'mscorlib.dll', 'WindowsBase.dll', 'PresentationCore.dll',
        'clrjit.dll', 'coreclr.dll', 'hostfxr.dll', 'hostpolicy.dll',
        'WebBrowserInterop.*.dll', 'WebView2Loader.dll',
        'vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll', 'ucrtbase.dll',
        'api-ms-win-*.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['ui/afudm.ico'],
    version=_VERSION_RESOURCE,
)

