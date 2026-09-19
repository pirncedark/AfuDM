# -*- mode: python ; coding: utf-8 -*-


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
)

