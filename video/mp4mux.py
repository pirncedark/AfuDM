"""MP4 birlestirici — ayri inen video ve ses izini TEK mp4 dosyasinda toplar.

Neden var: YouTube 2026'da ses+video birlesik format VERMIYOR; iki iz ayri
iniyor. Birlestirme isini bugune kadar ffmpeg (97 MB) yapiyordu. Burasi o isin
YENIDEN KODLAMA YAPMAYAN kismini ustlenir, boylece cekirdek paket ffmpeg'siz de
sesli video uretebilir. (mp3'e cevirme gibi gercek donusumler yine ffmpeg ister.)

Yaptigi is "remux": iki dosyanin sikistirilmis ornekleri OLDUGU GIBI kopyalanir,
yalnizca konteyner yeniden yazilir. Goruntu kalitesi degismez.

Iki kaynak bicimi de desteklenir:
  - Parcalanmis (fragmented) MP4: moov'da mvex/trex, ardindan moof+mdat dizisi.
    YouTube'un video izi boyle gelir (~250 parca).
  - Duz MP4: moov icinde stbl tablolari (stts/stsz/stco...).
    yt-dlp'nin duzelttigi m4a boyle gelir.

Uretilen dosya DUZ MP4'tur: tek moov + tek mdat.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------- kutu okuma

KAPSAYICI = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"moof",
             b"traf", b"mvex", b"dinf"}


@dataclass
class Kutu:
    tur: bytes
    konum: int          # kutunun dosyadaki basi
    boyut: int          # basliK dahil toplam
    govde: int          # icerigin basladigi konum
    cocuklar: list["Kutu"] = field(default_factory=list)

    def bul(self, *yol: bytes) -> "Kutu | None":
        """bul(b"mdia", b"mdhd") — art arda cocuk arar."""
        dugum = self
        for tur in yol:
            sonraki = next((c for c in dugum.cocuklar if c.tur == tur), None)
            if sonraki is None:
                return None
            dugum = sonraki
        return dugum

    def hepsi(self, tur: bytes) -> list["Kutu"]:
        out = [c for c in self.cocuklar if c.tur == tur]
        for c in self.cocuklar:
            out.extend(c.hepsi(tur))
        return out


def _kutulari_oku(f, bas: int, bitis: int, derinlik: int = 0) -> list[Kutu]:
    kutular: list[Kutu] = []
    f.seek(bas)
    while f.tell() < bitis:
        konum = f.tell()
        basl = f.read(8)
        if len(basl) < 8:
            break
        boyut, tur = struct.unpack(">I4s", basl)
        govde = konum + 8
        if boyut == 1:
            buyuk = f.read(8)
            if len(buyuk) < 8:
                break
            boyut = struct.unpack(">Q", buyuk)[0]
            govde = konum + 16
        elif boyut == 0:
            boyut = bitis - konum
        if boyut < 8 or konum + boyut > bitis:
            break
        kutu = Kutu(tur=tur, konum=konum, boyut=boyut, govde=govde)
        if tur in KAPSAYICI and derinlik < 10:
            kutu.cocuklar = _kutulari_oku(f, govde, konum + boyut, derinlik + 1)
        f.seek(konum + boyut)
        kutular.append(kutu)
    return kutular


def _u32(veri: bytes, i: int) -> int:
    return struct.unpack_from(">I", veri, i)[0]


def _u64(veri: bytes, i: int) -> int:
    return struct.unpack_from(">Q", veri, i)[0]


# ---------------------------------------------------------------- veri yapilari


@dataclass
class Ornek:
    """Tek bir sikistirilmis birim (video karesi / ses paketi)."""
    ofset: int          # kaynak dosyadaki konum
    boyut: int
    sure: int           # iz timescale'i cinsinden
    cts: int = 0        # gosterim kaymasi (B-kare icin)
    anahtar: bool = True


@dataclass
class Iz:
    tur: str                    # "vide" | "soun"
    kodek: str                  # "avc1" | "mp4a" ...
    timescale: int
    stsd_ham: bytes             # stsd kutusu OLDUGU GIBI (avcC/esds icinde)
    ornekler: list[Ornek]
    kaynak: Path
    genislik: int = 0           # video icin (16.16 sabit noktali degil, tam sayi)
    yukseklik: int = 0

    @property
    def toplam_sure(self) -> int:
        return sum(o.sure for o in self.ornekler)


# ---------------------------------------------------------------- okuma


def _stsd_oku(f, stbl: Kutu) -> tuple[bytes, str, int, int]:
    stsd = next((c for c in stbl.cocuklar if c.tur == b"stsd"), None)
    if stsd is None:
        raise ValueError("stsd bulunamadi")
    f.seek(stsd.konum)
    ham = f.read(stsd.boyut)
    # ham: [4 boyut][4 'stsd'][4 surum/bayrak][4 giris sayisi][giris...]
    kodek = ham[20:24].decode("latin-1", "replace") if len(ham) >= 24 else "?"
    genislik = yukseklik = 0
    if len(ham) >= 56:
        # gorsel giris: ...[24 on_tanimli][2 genislik][2 yukseklik]
        genislik, yukseklik = struct.unpack_from(">HH", ham, 16 + 8 + 24)
    return ham, kodek, genislik, yukseklik


def _duz_ornekler(f, stbl: Kutu) -> list[Ornek]:
    """Parcalanmamis MP4: stts/stsz/stsc/stco tablolarindan ornekleri kur."""
    def oku(tur: bytes) -> bytes | None:
        kutu = next((c for c in stbl.cocuklar if c.tur == tur), None)
        if kutu is None:
            return None
        f.seek(kutu.govde)
        return f.read(kutu.konum + kutu.boyut - kutu.govde)

    stts, stsz, stsc = oku(b"stts"), oku(b"stsz"), oku(b"stsc")
    stco, co64, stss, ctts = oku(b"stco"), oku(b"co64"), oku(b"stss"), oku(b"ctts")
    if stts is None or stsz is None or stsc is None or (stco is None and co64 is None):
        raise ValueError("duz MP4 icin gerekli tablolar eksik")

    # --- ornek sureleri
    sureler: list[int] = []
    adet = _u32(stts, 4)
    i = 8
    for _ in range(adet):
        sayi, sure = _u32(stts, i), _u32(stts, i + 4)
        sureler.extend([sure] * sayi)
        i += 8

    # --- ornek boyutlari
    sabit = _u32(stsz, 4)
    toplam = _u32(stsz, 8)
    if sabit:
        boyutlar = [sabit] * toplam
    else:
        boyutlar = [_u32(stsz, 12 + 4 * k) for k in range(toplam)]

    # --- yigin (chunk) konumlari
    if stco is not None:
        yigin_ofset = [_u32(stco, 8 + 4 * k) for k in range(_u32(stco, 4))]
    else:
        yigin_ofset = [_u64(co64, 8 + 8 * k) for k in range(_u32(co64, 4))]

    # --- hangi yiginda kac ornek var
    girisler = []
    adet = _u32(stsc, 4)
    for k in range(adet):
        j = 8 + 12 * k
        girisler.append((_u32(stsc, j), _u32(stsc, j + 4)))  # ilk_yigin, ornek_sayisi
    yigin_ornek: list[int] = []
    for k, (ilk, sayi) in enumerate(girisler):
        son = girisler[k + 1][0] - 1 if k + 1 < len(girisler) else len(yigin_ofset)
        yigin_ornek.extend([sayi] * max(0, son - ilk + 1))
    while len(yigin_ornek) < len(yigin_ofset):
        yigin_ornek.append(yigin_ornek[-1] if yigin_ornek else 1)

    # --- anahtar kareler
    anahtarlar = set()
    if stss is not None:
        anahtarlar = {_u32(stss, 8 + 4 * k) for k in range(_u32(stss, 4))}  # 1 tabanli

    # --- gosterim kaymalari
    cts_liste: list[int] = []
    if ctts is not None:
        adet = _u32(ctts, 4)
        i = 8
        for _ in range(adet):
            sayi = _u32(ctts, i)
            kayma = struct.unpack_from(">i", ctts, i + 4)[0]
            cts_liste.extend([kayma] * sayi)
            i += 8

    ornekler: list[Ornek] = []
    sira = 0
    for yigin, ofset in enumerate(yigin_ofset):
        konum = ofset
        for _ in range(yigin_ornek[yigin] if yigin < len(yigin_ornek) else 0):
            if sira >= len(boyutlar):
                break
            ornekler.append(Ornek(
                ofset=konum,
                boyut=boyutlar[sira],
                sure=sureler[sira] if sira < len(sureler) else 0,
                cts=cts_liste[sira] if sira < len(cts_liste) else 0,
                anahtar=(not anahtarlar) or (sira + 1) in anahtarlar,
            ))
            konum += boyutlar[sira]
            sira += 1
    return ornekler


def _parcali_ornekler(f, dosya_boyutu: int, iz_kimlik: int, trex: dict) -> list[Ornek]:
    """Parcalanmis MP4: her moof/traf/trun icinden ornekleri topla."""
    ornekler: list[Ornek] = []
    ust = _kutulari_oku(f, 0, dosya_boyutu)
    for moof in (k for k in ust if k.tur == b"moof"):
        for traf in (c for c in moof.cocuklar if c.tur == b"traf"):
            tfhd = next((c for c in traf.cocuklar if c.tur == b"tfhd"), None)
            if tfhd is None:
                continue
            f.seek(tfhd.govde)
            veri = f.read(tfhd.konum + tfhd.boyut - tfhd.govde)
            bayraklar = int.from_bytes(veri[1:4], "big")
            kimlik = _u32(veri, 4)
            if kimlik != iz_kimlik:
                continue
            i = 8
            temel_ofset = moof.konum          # varsayilan: default-base-is-moof
            if bayraklar & 0x000001:          # base-data-offset-present
                temel_ofset = _u64(veri, i); i += 8
            if bayraklar & 0x000002:          # sample-description-index-present
                i += 4
            v_sure = _u32(veri, i) if bayraklar & 0x000008 else trex["sure"]
            if bayraklar & 0x000008:
                i += 4
            v_boyut = _u32(veri, i) if bayraklar & 0x000010 else trex["boyut"]
            if bayraklar & 0x000010:
                i += 4
            v_bayrak = _u32(veri, i) if bayraklar & 0x000020 else trex["bayrak"]

            for trun in (c for c in traf.cocuklar if c.tur == b"trun"):
                f.seek(trun.govde)
                t = f.read(trun.konum + trun.boyut - trun.govde)
                t_bayrak = int.from_bytes(t[1:4], "big")
                sayi = _u32(t, 4)
                j = 8
                konum = temel_ofset
                if t_bayrak & 0x000001:       # data-offset-present (isaretli)
                    konum += struct.unpack_from(">i", t, j)[0]
                    j += 4
                ilk_ornek_bayragi = None
                if t_bayrak & 0x000004:       # first-sample-flags-present
                    ilk_ornek_bayragi = _u32(t, j); j += 4
                for n in range(sayi):
                    sure = v_sure
                    boyut = v_boyut
                    bayrak = v_bayrak
                    cts = 0
                    if t_bayrak & 0x000100:
                        sure = _u32(t, j); j += 4
                    if t_bayrak & 0x000200:
                        boyut = _u32(t, j); j += 4
                    if t_bayrak & 0x000400:
                        bayrak = _u32(t, j); j += 4
                    if t_bayrak & 0x000800:
                        cts = struct.unpack_from(">i", t, j)[0]; j += 4
                    if n == 0 and ilk_ornek_bayragi is not None:
                        bayrak = ilk_ornek_bayragi
                    # bayragin 16. biti "sample_is_non_sync_sample"
                    anahtar = not (bayrak & 0x00010000)
                    ornekler.append(Ornek(ofset=konum, boyut=boyut, sure=sure,
                                          cts=cts, anahtar=anahtar))
                    konum += boyut
    return ornekler


def izi_oku(yol: str | Path) -> Iz:
    """Dosyadaki TEK izi ornek listesiyle birlikte okur.

    YouTube izleri tek izlidir; birden fazla iz varsa ilki alinir.
    """
    yol = Path(yol)
    boyut = yol.stat().st_size
    with yol.open("rb") as f:
        ust = _kutulari_oku(f, 0, boyut)
        moov = next((k for k in ust if k.tur == b"moov"), None)
        if moov is None:
            raise ValueError(f"{yol.name}: moov yok, MP4 degil")
        trak = next((c for c in moov.cocuklar if c.tur == b"trak"), None)
        if trak is None:
            raise ValueError(f"{yol.name}: trak yok")

        tkhd = trak.bul(b"tkhd")
        f.seek(tkhd.govde)
        t = f.read(tkhd.konum + tkhd.boyut - tkhd.govde)
        surum = t[0]
        # tkhd govdesi: [4 surum/bayrak][olusturma][degistirme][4 iz kimligi]
        # olusturma/degistirme v0'da 4'er, v1'de 8'er bayt.
        iz_kimlik = _u32(t, 20) if surum == 1 else _u32(t, 12)

        mdhd = trak.bul(b"mdia", b"mdhd")
        f.seek(mdhd.govde)
        m = f.read(mdhd.konum + mdhd.boyut - mdhd.govde)
        # mdhd govdesi: [4 surum/bayrak][olusturma][degistirme][4 timescale]
        timescale = _u32(m, 20) if m[0] == 1 else _u32(m, 12)

        hdlr = trak.bul(b"mdia", b"hdlr")
        f.seek(hdlr.govde + 8)
        tur = f.read(4).decode("latin-1", "replace")

        stbl = trak.bul(b"mdia", b"minf", b"stbl")
        stsd_ham, kodek, genislik, yukseklik = _stsd_oku(f, stbl)

        mvex = next((c for c in moov.cocuklar if c.tur == b"mvex"), None)
        if mvex is not None:
            trex_varsayilan = {"sure": 0, "boyut": 0, "bayrak": 0}
            for trex in (c for c in mvex.cocuklar if c.tur == b"trex"):
                f.seek(trex.govde)
                x = f.read(trex.konum + trex.boyut - trex.govde)
                if _u32(x, 4) == iz_kimlik:
                    trex_varsayilan = {"sure": _u32(x, 12), "boyut": _u32(x, 16),
                                       "bayrak": _u32(x, 20)}
            ornekler = _parcali_ornekler(f, boyut, iz_kimlik, trex_varsayilan)
        else:
            ornekler = _duz_ornekler(f, stbl)

    if not ornekler:
        raise ValueError(f"{yol.name}: hic ornek bulunamadi")
    return Iz(tur=tur, kodek=kodek, timescale=timescale, stsd_ham=stsd_ham,
              ornekler=ornekler, kaynak=yol, genislik=genislik, yukseklik=yukseklik)


# ---------------------------------------------------------------- yazma

def _kutu(tur: bytes, *parcalar: bytes) -> bytes:
    govde = b"".join(parcalar)
    return struct.pack(">I4s", 8 + len(govde), tur) + govde


def _tam(deger: int) -> bytes:
    return struct.pack(">I", deger)


BIRIM_MATRIS = b"".join(
    struct.pack(">I", v & 0xFFFFFFFF)
    for v in (0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)
)


def _yiginlar(iz: Iz, saniye: float = 1.0) -> list[list[Ornek]]:
    """Ornekleri ~1 saniyelik yiginlara boler.

    Neden: video ve ses ornekleri dosyada arka arkaya degil, DONUSUMLU durmali.
    Oynatici dosyayi bastan okurken her an iki izden de veri bulmali; yoksa
    yavas diskte veya ag uzerinden ses/goruntu takilir.
    """
    out: list[list[Ornek]] = []
    mevcut: list[Ornek] = []
    birikmis = 0
    esik = max(1, int(iz.timescale * saniye))
    for o in iz.ornekler:
        mevcut.append(o)
        birikmis += o.sure
        if birikmis >= esik:
            out.append(mevcut)
            mevcut, birikmis = [], 0
    if mevcut:
        out.append(mevcut)
    return out


def _stts(ornekler: list[Ornek]) -> bytes:
    girisler: list[list[int]] = []
    for o in ornekler:
        if girisler and girisler[-1][1] == o.sure:
            girisler[-1][0] += 1
        else:
            girisler.append([1, o.sure])
    govde = _tam(0) + _tam(len(girisler))
    govde += b"".join(_tam(a) + _tam(b) for a, b in girisler)
    return _kutu(b"stts", govde)


def _ctts(ornekler: list[Ornek]):
    """Gosterim kaymasi tablosu — B-kare yoksa hic yazilmaz."""
    if all(o.cts == 0 for o in ornekler):
        return None
    girisler: list[list[int]] = []
    for o in ornekler:
        if girisler and girisler[-1][1] == o.cts:
            girisler[-1][0] += 1
        else:
            girisler.append([1, o.cts])
    govde = _tam(0) + _tam(len(girisler))
    govde += b"".join(_tam(a) + struct.pack(">i", b) for a, b in girisler)
    return _kutu(b"ctts", govde)


def _stss(ornekler: list[Ornek]):
    """Anahtar kare tablosu. HEPSI anahtarsa yazilmaz (standart boyle ister)."""
    if all(o.anahtar for o in ornekler):
        return None
    sira = [i + 1 for i, o in enumerate(ornekler) if o.anahtar]
    return _kutu(b"stss", _tam(0) + _tam(len(sira)) + b"".join(_tam(s) for s in sira))


def _stsc(yigin_boyutlari: list[int]) -> bytes:
    girisler: list[tuple[int, int]] = []
    for i, sayi in enumerate(yigin_boyutlari, start=1):
        if not girisler or girisler[-1][1] != sayi:
            girisler.append((i, sayi))
    govde = _tam(0) + _tam(len(girisler))
    govde += b"".join(_tam(ilk) + _tam(sayi) + _tam(1) for ilk, sayi in girisler)
    return _kutu(b"stsc", govde)


def _stsz(ornekler: list[Ornek]) -> bytes:
    govde = _tam(0) + _tam(0) + _tam(len(ornekler))
    govde += b"".join(_tam(o.boyut) for o in ornekler)
    return _kutu(b"stsz", govde)


def _stco(ofsetler: list[int]) -> bytes:
    """4 GB'i asan dosyada 64 bitlik co64'e gecer."""
    if ofsetler and max(ofsetler) >= 2 ** 32 - 1:
        govde = _tam(0) + _tam(len(ofsetler))
        govde += b"".join(struct.pack(">Q", o) for o in ofsetler)
        return _kutu(b"co64", govde)
    govde = _tam(0) + _tam(len(ofsetler))
    govde += b"".join(_tam(o) for o in ofsetler)
    return _kutu(b"stco", govde)


def _trak(iz: Iz, iz_no: int, film_timescale: int,
          yigin_ofsetleri: list[int], yigin_boyutlari: list[int]) -> bytes:
    sure_iz = iz.toplam_sure
    sure_film = int(sure_iz * film_timescale / iz.timescale)
    video_mu = iz.tur == "vide"

    tkhd = _kutu(
        b"tkhd",
        struct.pack(">I", 0x00000007),        # surum 0 + bayrak: acik, filmde
        _tam(0), _tam(0),                     # olusturma / degistirme
        _tam(iz_no), _tam(0), _tam(sure_film),
        _tam(0), _tam(0),                     # ayrilmis
        struct.pack(">hh", 0, 0),             # katman, alternatif grup
        struct.pack(">h", 0 if video_mu else 0x0100),   # ses seviyesi
        struct.pack(">h", 0),
        BIRIM_MATRIS,
        struct.pack(">II", iz.genislik << 16, iz.yukseklik << 16) if video_mu
        else struct.pack(">II", 0, 0),
    )

    mdhd = _kutu(b"mdhd", _tam(0), _tam(0), _tam(0),
                 _tam(iz.timescale), _tam(sure_iz),
                 struct.pack(">HH", 0x55C4, 0))          # dil kodu "und"

    ad = b"VideoHandler\x00" if video_mu else b"SoundHandler\x00"
    hdlr = _kutu(b"hdlr", _tam(0), _tam(0),
                 b"vide" if video_mu else b"soun",
                 _tam(0), _tam(0), _tam(0), ad)

    basli_kutu = (_kutu(b"vmhd", _tam(1), struct.pack(">HHH", 0, 0, 0))
                  if video_mu else _kutu(b"smhd", _tam(0), struct.pack(">hh", 0, 0)))
    dinf = _kutu(b"dinf", _kutu(b"dref", _tam(0), _tam(1), _kutu(b"url ", _tam(1))))

    parcalar = [iz.stsd_ham, _stts(iz.ornekler)]
    ctts = _ctts(iz.ornekler)
    if ctts:
        parcalar.append(ctts)
    stss = _stss(iz.ornekler)
    if stss:
        parcalar.append(stss)
    parcalar += [_stsc(yigin_boyutlari), _stsz(iz.ornekler), _stco(yigin_ofsetleri)]

    stbl = _kutu(b"stbl", *parcalar)
    minf = _kutu(b"minf", basli_kutu, dinf, stbl)
    mdia = _kutu(b"mdia", mdhd, hdlr, minf)

    # --- duzenleme listesi (elst): gosterim kaymasini kirpar ---
    # B-kare kullanan videoda ilk ornegin gosterim kaymasi (cts) sifir DEGILDIR;
    # ornegin burada 512 tik = tam bir kare. Duzeltilmezse video sese gore BIR
    # KARE GEC baslar — kulakla zor, dudak senkronunda fark edilir. Cozum ffmpeg'in
    # yaptiginin aynisi: "medyayi su andan itibaren goster" diyen bir elst yaz.
    dts = 0
    en_kucuk_pts = None
    for o in iz.ornekler:
        pts = dts + o.cts
        if en_kucuk_pts is None or pts < en_kucuk_pts:
            en_kucuk_pts = pts
        dts += o.sure
    elst = _kutu(b"elst", _tam(0), _tam(1),
                 _tam(sure_film), struct.pack(">i", en_kucuk_pts or 0),
                 _tam(0x00010000))
    edts = _kutu(b"edts", elst)

    return _kutu(b"trak", tkhd, edts, mdia)


def _moov(izler: list[Iz], film_timescale: int,
          ofsetler: list[list[int]], boyutlar: list[list[int]]) -> bytes:
    en_uzun = max(int(iz.toplam_sure * film_timescale / iz.timescale) for iz in izler)
    mvhd = _kutu(b"mvhd", _tam(0), _tam(0), _tam(0),
                 _tam(film_timescale), _tam(en_uzun),
                 _tam(0x00010000),                        # hiz 1.0
                 struct.pack(">h", 0x0100), struct.pack(">h", 0),   # ses 1.0
                 _tam(0), _tam(0),
                 BIRIM_MATRIS,
                 b"".join(_tam(0) for _ in range(6)),     # on_tanimli
                 _tam(len(izler) + 1))
    traklar = [_trak(iz, i + 1, film_timescale, ofsetler[i], boyutlar[i])
               for i, iz in enumerate(izler)]
    return _kutu(b"moov", mvhd, *traklar)


def birlestir(video_yolu, ses_yolu, hedef, ilerleme=None) -> dict:
    """Ayri video ve ses izini tek mp4'te toplar.

    Yeniden kodlama YOK: sikistirilmis ornekler oldugu gibi kopyalanir, yalnizca
    konteyner yeniden yazilir. Goruntu ve ses kalitesi degismez.
    ilerleme(yazilan_bayt, toplam_bayt) geri cagrilir.
    """
    video = izi_oku(video_yolu)
    ses = izi_oku(ses_yolu)
    if video.tur != "vide":
        raise ValueError("video dosyasinda video izi yok (%s)" % video.tur)
    if ses.tur != "soun":
        raise ValueError("ses dosyasinda ses izi yok (%s)" % ses.tur)

    izler = [video, ses]
    film_timescale = 1000
    yigin_listeleri = [_yiginlar(iz) for iz in izler]

    # Donusumlu sira: video0, ses0, video1, ses1, ...
    sira: list[tuple[int, list[Ornek]]] = []
    for i in range(max(len(y) for y in yigin_listeleri)):
        for iz_no, yiginlar in enumerate(yigin_listeleri):
            if i < len(yiginlar):
                sira.append((iz_no, yiginlar[i]))

    yigin_boyutlari = [[len(y) for y in yiginlar] for yiginlar in yigin_listeleri]
    toplam_veri = sum(o.boyut for iz in izler for o in iz.ornekler)

    def ofsetleri_hesapla(mdat_govde_basi: int) -> list[list[int]]:
        ofsetler: list[list[int]] = [[] for _ in izler]
        konum = mdat_govde_basi
        for iz_no, yigin in sira:
            ofsetler[iz_no].append(konum)
            konum += sum(o.boyut for o in yigin)
        return ofsetler

    ftyp = _kutu(b"ftyp", b"isom", _tam(0x200), b"isom", b"iso2", b"avc1", b"mp41")

    # moov'un boyutu ofsetlere, ofsetler de moov'un boyutuna bagli. Iki gecisle
    # cozulur: tablolar sabit genislikte oldugu icin ikinci gecis boyutu DEGISTIRMEZ.
    gecici = _moov(izler, film_timescale, ofsetleri_hesapla(0), yigin_boyutlari)
    buyuk_mdat = toplam_veri + 8 >= 2 ** 32
    mdat_basligi = 16 if buyuk_mdat else 8
    mdat_govde_basi = len(ftyp) + len(gecici) + mdat_basligi
    moov = _moov(izler, film_timescale, ofsetleri_hesapla(mdat_govde_basi), yigin_boyutlari)
    if len(moov) != len(gecici):
        # Olmamali. Olursa butun ofsetler kayar; sessizce bozuk dosya uretmektense dur.
        raise RuntimeError("moov boyutu degisti (%d -> %d)" % (len(gecici), len(moov)))

    hedef = Path(hedef)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    yazilan = 0
    with hedef.open("wb") as cikti, \
            Path(video_yolu).open("rb") as vf, Path(ses_yolu).open("rb") as sf:
        cikti.write(ftyp)
        cikti.write(moov)
        if buyuk_mdat:
            cikti.write(struct.pack(">I4sQ", 1, b"mdat", toplam_veri + 16))
        else:
            cikti.write(struct.pack(">I4s", toplam_veri + 8, b"mdat"))
        kaynaklar = (vf, sf)
        for iz_no, yigin in sira:
            f = kaynaklar[iz_no]
            for o in yigin:
                f.seek(o.ofset)
                veri = f.read(o.boyut)
                if len(veri) != o.boyut:
                    raise RuntimeError("kaynak dosya beklenenden kisa — indirme yarim mi?")
                cikti.write(veri)
                yazilan += o.boyut
            if ilerleme:
                ilerleme(yazilan, toplam_veri)

    return {
        "dosya": str(hedef),
        "boyut": hedef.stat().st_size,
        "video_ornek": len(video.ornekler),
        "ses_ornek": len(ses.ornekler),
        "sure_sn": round(video.toplam_sure / video.timescale, 2),
        "kodekler": "%s+%s" % (video.kodek, ses.kodek),
    }
