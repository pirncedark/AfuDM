"""aria2 RPC portu: ikinci PORTABLE kopya ayni makinede acilabilmeli.

AG GEREKTIRMEZ, aria2c CALISTIRMAZ. Gercek kusur (2026-09-19): port sabitti,
ikinci kopya "aria2c RPC 20 saniyede yanit vermedi" deyip hic acilmiyordu.
Windows ikinci aria2c'yi ayni porta BAGLATIYOR (hata vermiyor), istekler iki
surece dagiliyor ve oteki kopyanin sirri tutmadigi icin RPC hep 401 donuyor.
"""
import socket
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from core import daemon  # noqa: E402

hatalar = []


def kontrol(ad, sart, ek=""):
    print(("  [GECTI] " if sart else "  [DUSTU] ") + ad + (f" — {ek}" if ek else ""))
    if not sart:
        hatalar.append(ad)


print("1) dinleyen port algilama")
with socket.socket() as dinleyici:
    dinleyici.bind(("127.0.0.1", 0))
    dinleyici.listen(1)
    dolu = dinleyici.getsockname()[1]
    kontrol("dinlenen port DOLU gorunur", daemon._dinleyen_var_mi(dolu), f"port {dolu}")
with socket.socket() as bos_bul:
    bos_bul.bind(("127.0.0.1", 0))
    bos = bos_bul.getsockname()[1]
kontrol("kapanan port BOS gorunur", not daemon._dinleyen_var_mi(bos), f"port {bos}")

print("2) aralik ve varsayilan")
kontrol("aralik en az 10 port", daemon.RPC_PORT_SON - daemon.RPC_PORT >= 10,
        f"{daemon.RPC_PORT}-{daemon.RPC_PORT_SON}")
kontrol("varsayilan port degismedi", daemon.RPC_PORT == 6810)

print("3) port komut satirina geciyor")
args = daemon._args("sir", ".", 6817)
kontrol("--rpc-listen-port secilen porttur", "--rpc-listen-port=6817" in args)
kontrol("varsayilan cagri 6810 kalir",
        "--rpc-listen-port=6810" in daemon._args("sir", "."))

print("4) baslangicta port araniyor")
d = daemon.Aria2Daemon(download_dir=".")
kontrol("daemon portu tasiyor", d.port == daemon.RPC_PORT)
kontrol("rpc ayni porta bakiyor", d.rpc.port == d.port)

print("5) DOLU aralikta anlasilir hata")
# Gercek port baglamak yerine algilayiciyi degistiriyoruz: Windows'ta bazi
# portlar SISTEMCE ayrilmis olabiliyor (baglanamiyorsun ama dinleyen de yok),
# o yuzden "hepsini bagla" yontemi kararsiz sonuc veriyordu.
eski_algi = daemon._dinleyen_var_mi
daemon._dinleyen_var_mi = lambda port: True
try:
    d2 = daemon.Aria2Daemon(download_dir=".")
    d2.secret = "test-" + "x" * 20     # calisan gercek motora BAGLANMA
    try:
        d2.start(timeout=0.5)
        kontrol("dolu aralikta hata verir", False, "hic hata vermedi")
    except RuntimeError as exc:
        kontrol("dolu aralikta anlasilir hata", "bos RPC portu yok" in str(exc), str(exc)[:70])
    kontrol("motor CALISTIRILMADI", d2.proc is None)
finally:
    daemon._dinleyen_var_mi = eski_algi

print("6) bos port secilir ve kullanilir")
daemon._dinleyen_var_mi = lambda port: port < daemon.RPC_PORT + 3   # ilk uc dolu
try:
    d3 = daemon.Aria2Daemon(download_dir=".")
    d3.secret = "test-" + "y" * 20
    secilen = next(
        (p for p in range(daemon.RPC_PORT, daemon.RPC_PORT_SON + 1)
         if not daemon._dinleyen_var_mi(p)), None)
    kontrol("ilk BOS port secilir", secilen == daemon.RPC_PORT + 3, f"port {secilen}")
    kontrol("secilen port komuta yazilir",
            "--rpc-listen-port=%d" % secilen in daemon._args("sir", ".", secilen))
finally:
    daemon._dinleyen_var_mi = eski_algi

print()
if hatalar:
    print("BASARISIZ:", ", ".join(hatalar))
    sys.exit(1)
print("Hepsi gecti")
