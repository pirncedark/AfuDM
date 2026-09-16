"""MP4 kutu (box/atom) okuyucu — SADECE OKUR, dosyaya dokunmaz.

Neden var: YouTube sesi ve goruntuyu ayri gonderiyor (2026 olcumu: birlesik
format YOK). Kendi birlestiricimizi yazabilmemiz icin once su sorunun cevabi
lazim: elimize gelen iki dosya gercekten birlestirilebilir mi?

Birlestirilebilmesi icin ikisinin de:
  - MP4 ailesinden olmasi (ftyp kutusu),
  - PARCALANMIS (fragmented) OLMAMASI — yani `moof` kutusu bulunmamasi,
  - okunabilir bir `moov` icinde tek bir iz (`trak`) tasimasi gerekir.

Parcalanmis MP4'te ornek tablolari her parcaya dagilir; birlestirme cok daha
zor olur. Bu modul bunu OLCER, tahmin etmez.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

# Icinde baska kutular barindiran kutular — icine inilir.
KAPSAYICI = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"moof", b"traf"}


@dataclass
class Kutu:
    tur: str
    boyut: int
    konum: int
    cocuklar: list["Kutu"] = field(default_factory=list)

    def bul(self, tur: str) -> "Kutu | None":
        if self.tur == tur:
            return self
        for c in self.cocuklar:
            found = c.bul(tur)
            if found is not None:
                return found
        return None

    def hepsi(self, tur: str) -> list["Kutu"]:
        out = [self] if self.tur == tur else []
        for c in self.cocuklar:
            out.extend(c.hepsi(tur))
        return out


def _oku(f, bitis: int, derinlik: int = 0) -> list[Kutu]:
    kutular: list[Kutu] = []
    while f.tell() < bitis:
        konum = f.tell()
        basl = f.read(8)
        if len(basl) < 8:
            break
        boyut, tur = struct.unpack(">I4s", basl)
        govde = konum + 8
        if boyut == 1:                      # 64 bitlik boyut
            buyuk = f.read(8)
            if len(buyuk) < 8:
                break
            boyut = struct.unpack(">Q", buyuk)[0]
            govde = konum + 16
        elif boyut == 0:                    # dosyanin sonuna kadar
            boyut = bitis - konum
        if boyut < 8 or konum + boyut > bitis:
            break
        kutu = Kutu(tur=tur.decode("latin-1"), boyut=boyut, konum=konum)
        if tur in KAPSAYICI and derinlik < 8:
            kutu.cocuklar = _oku(f, konum + boyut, derinlik + 1)
        f.seek(konum + boyut)
        kutular.append(kutu)
    return kutular


def incele(yol: str | Path) -> dict:
    """Dosyanin kutu yapisini ozetler."""
    yol = Path(yol)
    boyut = yol.stat().st_size
    with yol.open("rb") as f:
        ust = _oku(f, boyut)
    turler = [k.tur for k in ust]
    kok = Kutu(tur="(kok)", boyut=boyut, konum=0, cocuklar=ust)
    moov = kok.bul("moov")
    traklar = moov.hepsi("trak") if moov else []
    izler = []
    for trak in traklar:
        hdlr = trak.bul("hdlr")
        tur = "?"
        if hdlr:
            with yol.open("rb") as f:
                f.seek(hdlr.konum + 16)     # 8 basl + 4 surum/bayrak + 4 on_tanimli
                tur = f.read(4).decode("latin-1", "replace")
        stsd = trak.bul("stsd")
        kodek = "?"
        if stsd:
            with yol.open("rb") as f:
                f.seek(stsd.konum + 20)     # basl + surum/bayrak + giris sayisi + giris boyutu
                kodek = f.read(4).decode("latin-1", "replace")
        izler.append({"tur": tur.strip(), "kodek": kodek.strip()})
    return {
        "dosya": yol.name,
        "boyut": boyut,
        "ust_kutular": turler,
        "mp4_mi": "ftyp" in turler,
        "parcalanmis_mi": bool(kok.bul("moof")) or bool(kok.bul("mvex")),
        "moov_var": moov is not None,
        "moov_konum": moov.konum if moov else -1,
        "iz_sayisi": len(traklar),
        "izler": izler,
    }


def birlestirilebilir_mi(video_yolu: str | Path, ses_yolu: str | Path) -> tuple[bool, str]:
    """Iki dosya kendi birlestiricimizle tek mp4'e dokunebilir mi?"""
    v = incele(video_yolu)
    s = incele(ses_yolu)
    for ad, bilgi in (("video", v), ("ses", s)):
        if not bilgi["mp4_mi"]:
            return False, f"{ad} dosyasi MP4 degil (ust kutular: {bilgi['ust_kutular']})"
        if bilgi["parcalanmis_mi"]:
            return False, f"{ad} dosyasi PARCALANMIS MP4 (moof/mvex) — cok daha zor"
        if not bilgi["moov_var"]:
            return False, f"{ad} dosyasinda moov yok"
        if bilgi["iz_sayisi"] != 1:
            return False, f"{ad} dosyasinda {bilgi['iz_sayisi']} iz var, 1 bekleniyordu"
    return True, (f"video {v['izler'][0]['kodek']} + ses {s['izler'][0]['kodek']}, "
                  f"ikisi de parcalanmamis MP4")
