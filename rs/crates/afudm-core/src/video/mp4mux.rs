//! MP4 birlestirici: ayri inen video ve ses izini TEK mp4 dosyasinda toplar.
//! Port of video/mp4mux.py. Yeniden kodlama YOK: ornekler oldugu gibi kopyalanir,
//! yalnizca konteyner yeniden yazilir. Iki kaynak bicimi desteklenir: parcalanmis
//! (moof/traf/trun) ve duz (stbl tablolari). Uretilen dosya duz MP4'tur.

use afudm_types::{AfuError, Result};
use std::collections::HashSet;
use std::fs::File;
use std::io::{BufWriter, Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

const KAPSAYICI: [[u8; 4]; 10] = [
    *b"moov", *b"trak", *b"mdia", *b"minf", *b"stbl", *b"edts", *b"moof", *b"traf", *b"mvex",
    *b"dinf",
];

fn bozuk(neden: &str) -> AfuError {
    AfuError::Invalid(format!("MP4 bozuk: {neden}"))
}

fn sabit<const N: usize>(v: &[u8], i: usize) -> Result<[u8; N]> {
    v.get(i..i.saturating_add(N))
        .and_then(|s| s.try_into().ok())
        .ok_or_else(|| bozuk("kisa veri"))
}

fn u32_at(v: &[u8], i: usize) -> Result<u32> {
    Ok(u32::from_be_bytes(sabit::<4>(v, i)?))
}

fn i32_at(v: &[u8], i: usize) -> Result<i32> {
    Ok(i32::from_be_bytes(sabit::<4>(v, i)?))
}

fn u64_at(v: &[u8], i: usize) -> Result<u64> {
    Ok(u64::from_be_bytes(sabit::<8>(v, i)?))
}

/// Python int.from_bytes(v[i:i+3], "big")
fn u24_at(v: &[u8], i: usize) -> Result<u32> {
    let b = sabit::<3>(v, i)?;
    Ok(u32::from_be_bytes([0, b[0], b[1], b[2]]))
}

/// Dosyadan `uzunluk` bayt oku (kisa okuma olabilir; Python f.read(n) ile ayni).
fn oku_konum(f: &mut File, konum: u64, uzunluk: u64) -> Result<Vec<u8>> {
    f.seek(SeekFrom::Start(konum))?;
    let mut v = Vec::new();
    Read::take(&mut *f, uzunluk).read_to_end(&mut v)?;
    Ok(v)
}

// ---------------------------------------------------------------- kutu okuma

#[derive(Debug, Clone)]
struct Kutu {
    tur: [u8; 4],
    konum: u64,
    boyut: u64,
    govde: u64,
    cocuklar: Vec<Kutu>,
}

impl Kutu {
    fn cocuk(&self, tur: &[u8; 4]) -> Option<&Kutu> {
        self.cocuklar.iter().find(|c| &c.tur == tur)
    }

    /// Python bul(*yol): art arda cocuk arar.
    fn bul(&self, yol: &[&[u8; 4]]) -> Option<&Kutu> {
        yol.iter().try_fold(self, |d, t| d.cocuk(t))
    }

    fn govde_uzunlugu(&self) -> u64 {
        self.konum + self.boyut - self.govde
    }
}

fn kutulari_oku(f: &mut File, bas: u64, bitis: u64, derinlik: u32) -> Result<Vec<Kutu>> {
    let mut kutular = Vec::new();
    let mut pos = bas;
    while pos < bitis {
        let basl = oku_konum(f, pos, 8)?;
        if basl.len() < 8 {
            break;
        }
        let mut boyut = u64::from(u32_at(&basl, 0)?);
        let tur: [u8; 4] = sabit(&basl, 4)?;
        let mut govde = pos + 8;
        if boyut == 1 {
            let buyuk = oku_konum(f, pos + 8, 8)?;
            if buyuk.len() < 8 {
                break;
            }
            boyut = u64_at(&buyuk, 0)?;
            govde = pos + 16;
        } else if boyut == 0 {
            boyut = bitis - pos;
        }
        if boyut < 8 || pos.saturating_add(boyut) > bitis {
            break;
        }
        let cocuklar = if KAPSAYICI.contains(&tur) && derinlik < 10 {
            kutulari_oku(f, govde, pos + boyut, derinlik + 1)?
        } else {
            Vec::new()
        };
        kutular.push(Kutu {
            tur,
            konum: pos,
            boyut,
            govde,
            cocuklar,
        });
        pos += boyut;
    }
    Ok(kutular)
}

// ---------------------------------------------------------------- veri yapilari

/// Tek bir sikistirilmis birim (video karesi / ses paketi).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Ornek {
    /// Kaynak dosyadaki konum.
    pub ofset: u64,
    pub boyut: u64,
    /// Iz timescale'i cinsinden sure.
    pub sure: u64,
    /// Gosterim kaymasi (B-kare icin).
    pub cts: i64,
    pub anahtar: bool,
}

#[derive(Debug, Clone)]
pub struct Iz {
    /// "vide" | "soun"
    pub tur: String,
    /// "avc1" | "mp4a" ...
    pub kodek: String,
    pub timescale: u64,
    /// stsd kutusu OLDUGU GIBI (avcC/esds icinde).
    pub stsd_ham: Vec<u8>,
    pub ornekler: Vec<Ornek>,
    #[allow(dead_code)] // Python Iz.kaynak; tanilama icin tutulur
    pub kaynak: PathBuf,
    /// Video icin tam sayi genislik/yukseklik.
    pub genislik: u32,
    pub yukseklik: u32,
}

impl Iz {
    pub fn toplam_sure(&self) -> u64 {
        self.ornekler.iter().map(|o| o.sure).sum()
    }
}

#[derive(Debug, Clone, Copy)]
struct Trex {
    sure: u64,
    boyut: u64,
    bayrak: u32,
}

// ---------------------------------------------------------------- okuma

fn tablo(f: &mut File, stbl: &Kutu, tur: &[u8; 4]) -> Result<Option<Vec<u8>>> {
    match stbl.cocuk(tur) {
        Some(k) => Ok(Some(oku_konum(f, k.govde, k.govde_uzunlugu())?)),
        None => Ok(None),
    }
}

fn stsd_oku(f: &mut File, stbl: &Kutu) -> Result<(Vec<u8>, String, u32, u32)> {
    let stsd = stbl
        .cocuk(b"stsd")
        .ok_or_else(|| bozuk("stsd bulunamadi"))?;
    let ham = oku_konum(f, stsd.konum, stsd.boyut)?;
    let kodek: String = if ham.len() >= 24 {
        ham[20..24].iter().map(|&b| char::from(b)).collect()
    } else {
        "?".to_string()
    };
    let (mut genislik, mut yukseklik) = (0u32, 0u32);
    if ham.len() >= 56 {
        genislik = u32::from(u16::from_be_bytes(sabit::<2>(&ham, 48)?));
        yukseklik = u32::from(u16::from_be_bytes(sabit::<2>(&ham, 50)?));
    }
    Ok((ham, kodek, genislik, yukseklik))
}

/// Parcalanmamis MP4: stts/stsz/stsc/stco tablolarindan ornekleri kur.
fn duz_ornekler(f: &mut File, stbl: &Kutu) -> Result<Vec<Ornek>> {
    let stts = tablo(f, stbl, b"stts")?;
    let stsz = tablo(f, stbl, b"stsz")?;
    let stsc = tablo(f, stbl, b"stsc")?;
    let stco = tablo(f, stbl, b"stco")?;
    let co64 = tablo(f, stbl, b"co64")?;
    let stss = tablo(f, stbl, b"stss")?;
    let ctts = tablo(f, stbl, b"ctts")?;
    let (Some(stts), Some(stsz), Some(stsc)) = (stts, stsz, stsc) else {
        return Err(bozuk("duz MP4 icin gerekli tablolar eksik"));
    };
    if stco.is_none() && co64.is_none() {
        return Err(bozuk("duz MP4 icin gerekli tablolar eksik"));
    }

    // Ornek sureleri
    let mut sureler: Vec<u64> = Vec::new();
    for k in 0..u32_at(&stts, 4)? as usize {
        let sayi = u32_at(&stts, 8 + 8 * k)?;
        let sure = u64::from(u32_at(&stts, 12 + 8 * k)?);
        sureler.extend(std::iter::repeat_n(sure, sayi as usize));
    }

    // Ornek boyutlari
    let sabit_boyut = u32_at(&stsz, 4)?;
    let toplam = u32_at(&stsz, 8)? as usize;
    let boyutlar: Vec<u64> = if sabit_boyut != 0 {
        vec![u64::from(sabit_boyut); toplam]
    } else {
        (0..toplam)
            .map(|k| u32_at(&stsz, 12 + 4 * k).map(u64::from))
            .collect::<Result<_>>()?
    };

    // Yigin (chunk) konumlari
    let yigin_ofset: Vec<u64> = if let Some(s) = &stco {
        (0..u32_at(s, 4)? as usize)
            .map(|k| u32_at(s, 8 + 4 * k).map(u64::from))
            .collect::<Result<_>>()?
    } else if let Some(c) = &co64 {
        (0..u32_at(c, 4)? as usize)
            .map(|k| u64_at(c, 8 + 8 * k))
            .collect::<Result<_>>()?
    } else {
        return Err(bozuk("yigin tablosu yok"));
    };

    // Hangi yiginda kac ornek var
    let mut girisler: Vec<(u32, u32)> = Vec::new();
    for k in 0..u32_at(&stsc, 4)? as usize {
        let j = 8 + 12 * k;
        girisler.push((u32_at(&stsc, j)?, u32_at(&stsc, j + 4)?));
    }
    let mut yigin_ornek: Vec<u64> = Vec::new();
    for (k, &(ilk, sayi)) in girisler.iter().enumerate() {
        let son: i64 = match girisler.get(k + 1) {
            Some(&(sonraki, _)) => i64::from(sonraki) - 1,
            None => yigin_ofset.len() as i64,
        };
        let adet = (son - i64::from(ilk) + 1).max(0) as usize;
        yigin_ornek.extend(std::iter::repeat_n(u64::from(sayi), adet));
    }
    while yigin_ornek.len() < yigin_ofset.len() {
        let son = yigin_ornek.last().copied().unwrap_or(1);
        yigin_ornek.push(son);
    }

    // Anahtar kareler (1 tabanli)
    let anahtarlar: HashSet<u32> = match &stss {
        Some(s) => (0..u32_at(s, 4)? as usize)
            .map(|k| u32_at(s, 8 + 4 * k))
            .collect::<Result<_>>()?,
        None => HashSet::new(),
    };

    // Gosterim kaymalari
    let mut cts_liste: Vec<i64> = Vec::new();
    if let Some(c) = &ctts {
        let surumu1 = c.first() == Some(&1);
        for k in 0..u32_at(c, 4)? as usize {
            let sayi = u32_at(c, 8 + 8 * k)?;
            let kayma = if surumu1 {
                i64::from(i32_at(c, 12 + 8 * k)?)
            } else {
                i64::from(u32_at(c, 12 + 8 * k)?)
            };
            cts_liste.extend(std::iter::repeat_n(kayma, sayi as usize));
        }
    }

    let mut ornekler = Vec::new();
    let mut sira = 0usize;
    for (yigin, &ofset) in yigin_ofset.iter().enumerate() {
        let mut konum = ofset;
        let n = yigin_ornek.get(yigin).copied().unwrap_or(0);
        for _ in 0..n {
            if sira >= boyutlar.len() {
                break;
            }
            ornekler.push(Ornek {
                ofset: konum,
                boyut: boyutlar[sira],
                sure: sureler.get(sira).copied().unwrap_or(0),
                cts: cts_liste.get(sira).copied().unwrap_or(0),
                anahtar: anahtarlar.is_empty() || anahtarlar.contains(&((sira + 1) as u32)),
            });
            konum += boyutlar[sira];
            sira += 1;
        }
    }
    Ok(ornekler)
}

/// Parcalanmis MP4: her moof/traf/trun icinden ornekleri topla.
fn parcali_ornekler(
    f: &mut File,
    dosya_boyutu: u64,
    iz_kimlik: u32,
    trex: Trex,
) -> Result<Vec<Ornek>> {
    let mut ornekler = Vec::new();
    let ust = kutulari_oku(f, 0, dosya_boyutu, 0)?;
    for moof in ust.iter().filter(|k| &k.tur == b"moof") {
        for traf in moof.cocuklar.iter().filter(|c| &c.tur == b"traf") {
            let Some(tfhd) = traf.cocuk(b"tfhd") else {
                continue;
            };
            let veri = oku_konum(f, tfhd.govde, tfhd.govde_uzunlugu())?;
            let bayraklar = u24_at(&veri, 1)?;
            let kimlik = u32_at(&veri, 4)?;
            if kimlik != iz_kimlik {
                continue;
            }
            let mut i = 8usize;
            let mut temel_ofset = moof.konum; // default-base-is-moof
            if bayraklar & 0x01 != 0 {
                temel_ofset = u64_at(&veri, i)?;
                i += 8;
            }
            if bayraklar & 0x02 != 0 {
                i += 4;
            }
            let v_sure = if bayraklar & 0x08 != 0 {
                let v = u64::from(u32_at(&veri, i)?);
                i += 4;
                v
            } else {
                trex.sure
            };
            let v_boyut = if bayraklar & 0x10 != 0 {
                let v = u64::from(u32_at(&veri, i)?);
                i += 4;
                v
            } else {
                trex.boyut
            };
            let v_bayrak = if bayraklar & 0x20 != 0 {
                u32_at(&veri, i)?
            } else {
                trex.bayrak
            };

            let mut sonraki_ofset = temel_ofset;
            for trun in traf.cocuklar.iter().filter(|c| &c.tur == b"trun") {
                let t = oku_konum(f, trun.govde, trun.govde_uzunlugu())?;
                let t_bayrak = u24_at(&t, 1)?;
                let sayi = u32_at(&t, 4)?;
                let mut j = 8usize;
                let mut konum = sonraki_ofset;
                if t_bayrak & 0x01 != 0 {
                    // data-offset-present (isaretli)
                    konum = temel_ofset.wrapping_add_signed(i64::from(i32_at(&t, j)?));
                    j += 4;
                }
                let mut ilk_bayrak: Option<u32> = None;
                if t_bayrak & 0x04 != 0 {
                    ilk_bayrak = Some(u32_at(&t, j)?);
                    j += 4;
                }
                for n in 0..sayi {
                    let mut sure = v_sure;
                    let mut boyut = v_boyut;
                    let mut bayrak = v_bayrak;
                    let mut cts: i64 = 0;
                    if t_bayrak & 0x100 != 0 {
                        sure = u64::from(u32_at(&t, j)?);
                        j += 4;
                    }
                    if t_bayrak & 0x200 != 0 {
                        boyut = u64::from(u32_at(&t, j)?);
                        j += 4;
                    }
                    if t_bayrak & 0x400 != 0 {
                        bayrak = u32_at(&t, j)?;
                        j += 4;
                    }
                    if t_bayrak & 0x800 != 0 {
                        cts = if t.first() == Some(&1) {
                            i64::from(i32_at(&t, j)?)
                        } else {
                            i64::from(u32_at(&t, j)?)
                        };
                        j += 4;
                    }
                    if n == 0 {
                        if let Some(b) = ilk_bayrak {
                            bayrak = b;
                        }
                    }
                    // bayragin 16. biti "sample_is_non_sync_sample"
                    let anahtar = bayrak & 0x0001_0000 == 0;
                    ornekler.push(Ornek {
                        ofset: konum,
                        boyut,
                        sure,
                        cts,
                        anahtar,
                    });
                    konum += boyut;
                }
                sonraki_ofset = konum;
            }
        }
    }
    Ok(ornekler)
}

/// Dosyadaki TEK izi ornek listesiyle birlikte okur (ilk trak).
pub fn izi_oku(yol: &Path) -> Result<Iz> {
    let ad = yol
        .file_name()
        .map(|a| a.to_string_lossy().into_owned())
        .unwrap_or_default();
    let boyut = std::fs::metadata(yol)?.len();
    let mut f = File::open(yol)?;
    let ust = kutulari_oku(&mut f, 0, boyut, 0)?;
    let moov = ust
        .iter()
        .find(|k| &k.tur == b"moov")
        .ok_or_else(|| bozuk(&format!("{ad}: moov yok, MP4 degil")))?;
    let trak = moov
        .cocuk(b"trak")
        .ok_or_else(|| bozuk(&format!("{ad}: trak yok")))?;

    let tkhd = trak.cocuk(b"tkhd").ok_or_else(|| bozuk("tkhd yok"))?;
    let t = oku_konum(&mut f, tkhd.govde, tkhd.govde_uzunlugu())?;
    let surum = *t.first().ok_or_else(|| bozuk("tkhd bos"))?;
    // tkhd: [4 surum/bayrak][olusturma][degistirme][4 iz kimligi]; v1'de 8'er bayt.
    let iz_kimlik = if surum == 1 {
        u32_at(&t, 20)?
    } else {
        u32_at(&t, 12)?
    };

    let mdhd = trak
        .bul(&[b"mdia", b"mdhd"])
        .ok_or_else(|| bozuk("mdhd yok"))?;
    let m = oku_konum(&mut f, mdhd.govde, mdhd.govde_uzunlugu())?;
    let timescale = if m.first() == Some(&1) {
        u64::from(u32_at(&m, 20)?)
    } else {
        u64::from(u32_at(&m, 12)?)
    };

    let hdlr = trak
        .bul(&[b"mdia", b"hdlr"])
        .ok_or_else(|| bozuk("hdlr yok"))?;
    let tur_ham = oku_konum(&mut f, hdlr.govde + 8, 4)?;
    let tur: String = tur_ham.iter().map(|&b| char::from(b)).collect();

    let stbl = trak
        .bul(&[b"mdia", b"minf", b"stbl"])
        .ok_or_else(|| bozuk("stbl yok"))?;
    let (stsd_ham, kodek, genislik, yukseklik) = stsd_oku(&mut f, stbl)?;

    let ornekler = if let Some(mvex) = moov.cocuk(b"mvex") {
        let mut trex_varsayilan = Trex {
            sure: 0,
            boyut: 0,
            bayrak: 0,
        };
        for trex in mvex.cocuklar.iter().filter(|c| &c.tur == b"trex") {
            let x = oku_konum(&mut f, trex.govde, trex.govde_uzunlugu())?;
            if u32_at(&x, 4)? == iz_kimlik {
                trex_varsayilan = Trex {
                    sure: u64::from(u32_at(&x, 12)?),
                    boyut: u64::from(u32_at(&x, 16)?),
                    bayrak: u32_at(&x, 20)?,
                };
            }
        }
        parcali_ornekler(&mut f, boyut, iz_kimlik, trex_varsayilan)?
    } else {
        duz_ornekler(&mut f, stbl)?
    };

    if ornekler.is_empty() {
        return Err(bozuk(&format!("{ad}: hic ornek bulunamadi")));
    }
    Ok(Iz {
        tur,
        kodek,
        timescale,
        stsd_ham,
        ornekler,
        kaynak: yol.to_path_buf(),
        genislik,
        yukseklik,
    })
}

// ---------------------------------------------------------------- yazma

fn kutu(tur: &[u8; 4], parcalar: &[&[u8]]) -> Vec<u8> {
    let govde: Vec<u8> = parcalar.concat();
    let mut v = Vec::with_capacity(8 + govde.len());
    v.extend_from_slice(&((8 + govde.len()) as u32).to_be_bytes());
    v.extend_from_slice(tur);
    v.extend_from_slice(&govde);
    v
}

fn tam(deger: u32) -> [u8; 4] {
    deger.to_be_bytes()
}

fn birim_matris() -> [u8; 36] {
    let mut m = [0u8; 36];
    for (i, v) in [0x0001_0000u32, 0, 0, 0, 0x0001_0000, 0, 0, 0, 0x4000_0000]
        .iter()
        .enumerate()
    {
        m[i * 4..i * 4 + 4].copy_from_slice(&v.to_be_bytes());
    }
    m
}

/// Ornekleri ~1 saniyelik yiginlara boler (video ve ses donusumlu okunsun diye).
fn yiginlar(iz: &Iz) -> Vec<Vec<Ornek>> {
    let mut out: Vec<Vec<Ornek>> = Vec::new();
    let mut mevcut: Vec<Ornek> = Vec::new();
    let mut birikmis: u64 = 0;
    let esik = (iz.timescale).max(1);
    for o in &iz.ornekler {
        mevcut.push(*o);
        birikmis += o.sure;
        if birikmis >= esik {
            out.push(std::mem::take(&mut mevcut));
            birikmis = 0;
        }
    }
    if !mevcut.is_empty() {
        out.push(mevcut);
    }
    out
}

/// Ayni degerleri ardisik ciftlerle (sayi, deger) kodlar.
fn calistir<T: PartialEq + Copy>(degerler: impl Iterator<Item = T>) -> Vec<(u32, T)> {
    let mut girisler: Vec<(u32, T)> = Vec::new();
    for d in degerler {
        match girisler.last_mut() {
            Some(son) if son.1 == d => son.0 += 1,
            _ => girisler.push((1, d)),
        }
    }
    girisler
}

fn stts(ornekler: &[Ornek]) -> Vec<u8> {
    let g = calistir(ornekler.iter().map(|o| o.sure));
    let mut govde = tam(0).to_vec();
    govde.extend_from_slice(&tam(g.len() as u32));
    for (a, b) in g {
        govde.extend_from_slice(&tam(a));
        govde.extend_from_slice(&tam(b as u32));
    }
    kutu(b"stts", &[&govde])
}

/// Gosterim kaymasi tablosu; B-kare yoksa hic yazilmaz.
fn ctts(ornekler: &[Ornek]) -> Option<Vec<u8>> {
    if ornekler.iter().all(|o| o.cts == 0) {
        return None;
    }
    let surum: u32 = if ornekler.iter().any(|o| o.cts < 0) {
        1
    } else {
        0
    };
    let g = calistir(ornekler.iter().map(|o| o.cts));
    let mut govde = tam(surum << 24).to_vec();
    govde.extend_from_slice(&tam(g.len() as u32));
    for (a, b) in g {
        govde.extend_from_slice(&tam(a));
        let deger = if surum == 1 {
            (b as i32).to_be_bytes()
        } else {
            (b as u32).to_be_bytes()
        };
        govde.extend_from_slice(&deger);
    }
    Some(kutu(b"ctts", &[&govde]))
}

/// Anahtar kare tablosu; HEPSI anahtarsa yazilmaz.
fn stss(ornekler: &[Ornek]) -> Option<Vec<u8>> {
    if ornekler.iter().all(|o| o.anahtar) {
        return None;
    }
    let sira: Vec<u32> = ornekler
        .iter()
        .enumerate()
        .filter(|(_, o)| o.anahtar)
        .map(|(i, _)| (i + 1) as u32)
        .collect();
    let mut govde = tam(0).to_vec();
    govde.extend_from_slice(&tam(sira.len() as u32));
    for s in sira {
        govde.extend_from_slice(&tam(s));
    }
    Some(kutu(b"stss", &[&govde]))
}

fn stsc(yigin_boyutlari: &[usize]) -> Vec<u8> {
    let mut girisler: Vec<(u32, u32)> = Vec::new();
    for (i, &sayi) in yigin_boyutlari.iter().enumerate() {
        let sayi = sayi as u32;
        if girisler.last().is_none_or(|son| son.1 != sayi) {
            girisler.push((i as u32 + 1, sayi));
        }
    }
    let mut govde = tam(0).to_vec();
    govde.extend_from_slice(&tam(girisler.len() as u32));
    for (ilk, sayi) in girisler {
        govde.extend_from_slice(&tam(ilk));
        govde.extend_from_slice(&tam(sayi));
        govde.extend_from_slice(&tam(1));
    }
    kutu(b"stsc", &[&govde])
}

fn stsz(ornekler: &[Ornek]) -> Vec<u8> {
    let mut govde = tam(0).to_vec();
    govde.extend_from_slice(&tam(0));
    govde.extend_from_slice(&tam(ornekler.len() as u32));
    for o in ornekler {
        govde.extend_from_slice(&tam(o.boyut as u32));
    }
    kutu(b"stsz", &[&govde])
}

/// 4 GB'i asan dosyada 64 bitlik co64'e gecer.
fn stco(ofsetler: &[u64]) -> Vec<u8> {
    let mut govde = tam(0).to_vec();
    govde.extend_from_slice(&tam(ofsetler.len() as u32));
    if ofsetler
        .iter()
        .max()
        .is_some_and(|&m| m >= u64::from(u32::MAX))
    {
        for &o in ofsetler {
            govde.extend_from_slice(&o.to_be_bytes());
        }
        kutu(b"co64", &[&govde])
    } else {
        for &o in ofsetler {
            govde.extend_from_slice(&tam(o as u32));
        }
        kutu(b"stco", &[&govde])
    }
}

fn trak(
    iz: &Iz,
    iz_no: u32,
    film_timescale: u64,
    yigin_ofsetleri: &[u64],
    yigin_boyutlari: &[usize],
) -> Vec<u8> {
    let sure_iz = iz.toplam_sure();
    let sure_film = (sure_iz as f64 * film_timescale as f64 / iz.timescale as f64) as u64;
    let video_mu = iz.tur == "vide";

    let mut tkhd_govde = 0x0000_0007u32.to_be_bytes().to_vec(); // surum 0 + bayrak: acik, filmde
    tkhd_govde.extend_from_slice(&tam(0));
    tkhd_govde.extend_from_slice(&tam(0));
    tkhd_govde.extend_from_slice(&tam(iz_no));
    tkhd_govde.extend_from_slice(&tam(0));
    tkhd_govde.extend_from_slice(&tam(sure_film as u32));
    tkhd_govde.extend_from_slice(&tam(0));
    tkhd_govde.extend_from_slice(&tam(0));
    tkhd_govde.extend_from_slice(&0i16.to_be_bytes()); // katman
    tkhd_govde.extend_from_slice(&0i16.to_be_bytes()); // alternatif grup
    tkhd_govde.extend_from_slice(&(if video_mu { 0i16 } else { 0x0100 }).to_be_bytes()); // ses
    tkhd_govde.extend_from_slice(&0i16.to_be_bytes());
    tkhd_govde.extend_from_slice(&birim_matris());
    if video_mu {
        tkhd_govde.extend_from_slice(&(iz.genislik << 16).to_be_bytes());
        tkhd_govde.extend_from_slice(&(iz.yukseklik << 16).to_be_bytes());
    } else {
        tkhd_govde.extend_from_slice(&[0u8; 8]);
    }
    let tkhd = kutu(b"tkhd", &[&tkhd_govde]);

    let mut mdhd_govde = tam(0).to_vec();
    mdhd_govde.extend_from_slice(&tam(0));
    mdhd_govde.extend_from_slice(&tam(0));
    mdhd_govde.extend_from_slice(&tam(iz.timescale as u32));
    mdhd_govde.extend_from_slice(&tam(sure_iz as u32));
    mdhd_govde.extend_from_slice(&0x55C4u16.to_be_bytes()); // dil kodu "und"
    mdhd_govde.extend_from_slice(&0u16.to_be_bytes());
    let mdhd = kutu(b"mdhd", &[&mdhd_govde]);

    let ad: &[u8] = if video_mu {
        b"VideoHandler\0"
    } else {
        b"SoundHandler\0"
    };
    let mut hdlr_govde = tam(0).to_vec();
    hdlr_govde.extend_from_slice(&tam(0));
    hdlr_govde.extend_from_slice(if video_mu { b"vide" } else { b"soun" });
    hdlr_govde.extend_from_slice(&tam(0));
    hdlr_govde.extend_from_slice(&tam(0));
    hdlr_govde.extend_from_slice(&tam(0));
    hdlr_govde.extend_from_slice(ad);
    let hdlr = kutu(b"hdlr", &[&hdlr_govde]);

    let basli_kutu = if video_mu {
        let mut g = tam(1).to_vec();
        g.extend_from_slice(&[0u8; 6]);
        kutu(b"vmhd", &[&g])
    } else {
        let mut g = tam(0).to_vec();
        g.extend_from_slice(&[0u8; 4]);
        kutu(b"smhd", &[&g])
    };
    let url_kutu = kutu(b"url ", &[&tam(1)]);
    let mut dref_govde = tam(0).to_vec();
    dref_govde.extend_from_slice(&tam(1));
    dref_govde.extend_from_slice(&url_kutu);
    let dref = kutu(b"dref", &[&dref_govde]);
    let dinf = kutu(b"dinf", &[&dref]);

    let mut stbl_parcalari: Vec<Vec<u8>> = vec![iz.stsd_ham.clone(), stts(&iz.ornekler)];
    if let Some(c) = ctts(&iz.ornekler) {
        stbl_parcalari.push(c);
    }
    if let Some(s) = stss(&iz.ornekler) {
        stbl_parcalari.push(s);
    }
    stbl_parcalari.push(stsc(yigin_boyutlari));
    stbl_parcalari.push(stsz(&iz.ornekler));
    stbl_parcalari.push(stco(yigin_ofsetleri));
    let refs: Vec<&[u8]> = stbl_parcalari.iter().map(Vec::as_slice).collect();
    let stbl = kutu(b"stbl", &refs);

    let minf = kutu(b"minf", &[&basli_kutu, &dinf, &stbl]);
    let mdia = kutu(b"mdia", &[&mdhd, &hdlr, &minf]);

    // Duzenleme listesi (elst): B-kare kullanan videoda ilk ornegin gosterim
    // kaymasi sifir degildir; medyayi o andan itibaren goster (ffmpeg'in yaptigi).
    let mut dts: i64 = 0;
    let mut en_kucuk_pts: Option<i64> = None;
    for o in &iz.ornekler {
        let pts = dts + o.cts;
        if en_kucuk_pts.is_none_or(|e| pts < e) {
            en_kucuk_pts = Some(pts);
        }
        dts += o.sure as i64;
    }
    let mut elst_govde = tam(0).to_vec();
    elst_govde.extend_from_slice(&tam(1));
    elst_govde.extend_from_slice(&tam(sure_film as u32));
    elst_govde.extend_from_slice(&(en_kucuk_pts.unwrap_or(0) as i32).to_be_bytes());
    elst_govde.extend_from_slice(&tam(0x0001_0000));
    let elst = kutu(b"elst", &[&elst_govde]);
    let edts = kutu(b"edts", &[&elst]);

    kutu(b"trak", &[&tkhd, &edts, &mdia])
}

fn moov(
    izler: &[Iz],
    film_timescale: u64,
    ofsetler: &[Vec<u64>],
    boyutlar: &[Vec<usize>],
) -> Vec<u8> {
    let en_uzun = izler
        .iter()
        .map(|iz| (iz.toplam_sure() as f64 * film_timescale as f64 / iz.timescale as f64) as u64)
        .max()
        .unwrap_or(0);
    let mut mvhd_govde = tam(0).to_vec();
    mvhd_govde.extend_from_slice(&tam(0));
    mvhd_govde.extend_from_slice(&tam(0));
    mvhd_govde.extend_from_slice(&tam(film_timescale as u32));
    mvhd_govde.extend_from_slice(&tam(en_uzun as u32));
    mvhd_govde.extend_from_slice(&tam(0x0001_0000)); // hiz 1.0
    mvhd_govde.extend_from_slice(&0x0100u16.to_be_bytes()); // ses 1.0
    mvhd_govde.extend_from_slice(&[0u8; 2]);
    mvhd_govde.extend_from_slice(&tam(0));
    mvhd_govde.extend_from_slice(&tam(0));
    mvhd_govde.extend_from_slice(&birim_matris());
    mvhd_govde.extend_from_slice(&[0u8; 24]); // on_tanimli
    mvhd_govde.extend_from_slice(&tam(izler.len() as u32 + 1));
    let mvhd = kutu(b"mvhd", &[&mvhd_govde]);

    let traklar: Vec<Vec<u8>> = izler
        .iter()
        .enumerate()
        .map(|(i, iz)| trak(iz, i as u32 + 1, film_timescale, &ofsetler[i], &boyutlar[i]))
        .collect();
    let mut refs: Vec<&[u8]> = vec![mvhd.as_slice()];
    refs.extend(traklar.iter().map(Vec::as_slice));
    kutu(b"moov", &refs)
}

/// Birlestirme sonucu (Python birlestir() dict'inin karsiligi).
#[allow(dead_code)] // alanlar ozet/gunluk icin; cagirana kadar okunmaz
#[derive(Debug, Clone, PartialEq)]
pub struct BirlestirOzeti {
    pub dosya: PathBuf,
    pub boyut: u64,
    pub video_ornek: usize,
    pub ses_ornek: usize,
    pub sure_sn: f64,
    pub kodekler: String,
}

/// Ayri video ve ses izini tek mp4'te toplar. Goruntu ve ses kalitesi degismez.
/// `ilerleme(yazilan, toplam)` her yiginda cagrilir.
pub fn birlestir(
    video_yolu: &Path,
    ses_yolu: &Path,
    hedef: &Path,
    ilerleme: Option<&dyn Fn(u64, u64)>,
) -> Result<BirlestirOzeti> {
    let video = izi_oku(video_yolu)?;
    let ses = izi_oku(ses_yolu)?;
    if video.tur != "vide" {
        return Err(AfuError::Invalid(format!(
            "video dosyasinda video izi yok ({})",
            video.tur
        )));
    }
    if ses.tur != "soun" {
        return Err(AfuError::Invalid(format!(
            "ses dosyasinda ses izi yok ({})",
            ses.tur
        )));
    }

    let izler = [video.clone(), ses.clone()];
    let film_timescale: u64 = 1000;
    let yigin_listeleri: Vec<Vec<Vec<Ornek>>> = izler.iter().map(yiginlar).collect();

    // Donusumlu sira: video0, ses0, video1, ses1, ...
    let mut sira: Vec<(usize, Vec<Ornek>)> = Vec::new();
    let en_cok = yigin_listeleri.iter().map(Vec::len).max().unwrap_or(0);
    for i in 0..en_cok {
        for (iz_no, yiginlar) in yigin_listeleri.iter().enumerate() {
            if let Some(y) = yiginlar.get(i) {
                sira.push((iz_no, y.clone()));
            }
        }
    }

    let yigin_boyutlari: Vec<Vec<usize>> = yigin_listeleri
        .iter()
        .map(|ys| ys.iter().map(Vec::len).collect())
        .collect();
    let toplam_veri: u64 = izler
        .iter()
        .flat_map(|iz| iz.ornekler.iter())
        .map(|o| o.boyut)
        .sum();

    let ofsetleri_hesapla = |mdat_govde_basi: u64| -> Vec<Vec<u64>> {
        let mut ofsetler: Vec<Vec<u64>> = vec![Vec::new(); izler.len()];
        let mut konum = mdat_govde_basi;
        for (iz_no, yigin) in &sira {
            ofsetler[*iz_no].push(konum);
            konum += yigin.iter().map(|o| o.boyut).sum::<u64>();
        }
        ofsetler
    };

    let ftyp = kutu(
        b"ftyp",
        &[b"isom", &tam(0x200), b"isom", b"iso2", b"avc1", b"mp41"],
    );

    // moov'un boyutu ofsetlere bagli; tablolar sabit genislikte, iki gecis yeter.
    let gecici = moov(
        &izler,
        film_timescale,
        &ofsetleri_hesapla(0),
        &yigin_boyutlari,
    );
    let buyuk_mdat = toplam_veri + 8 > u64::from(u32::MAX);
    let mdat_basligi: u64 = if buyuk_mdat { 16 } else { 8 };
    let mdat_govde_basi = ftyp.len() as u64 + gecici.len() as u64 + mdat_basligi;
    let moov_bytes = moov(
        &izler,
        film_timescale,
        &ofsetleri_hesapla(mdat_govde_basi),
        &yigin_boyutlari,
    );
    if moov_bytes.len() != gecici.len() {
        // Olmamali. Olursa butun ofsetler kayar; sessizce bozuk dosya uretmektense dur.
        return Err(AfuError::Other(format!(
            "moov boyutu degisti ({} -> {})",
            gecici.len(),
            moov_bytes.len()
        )));
    }

    if let Some(ust) = hedef.parent() {
        std::fs::create_dir_all(ust)?;
    }
    let mut cikti = BufWriter::new(File::create(hedef)?);
    let mut vf = File::open(video_yolu)?;
    let mut sf = File::open(ses_yolu)?;
    cikti.write_all(&ftyp)?;
    cikti.write_all(&moov_bytes)?;
    if buyuk_mdat {
        cikti.write_all(&1u32.to_be_bytes())?;
        cikti.write_all(b"mdat")?;
        cikti.write_all(&(toplam_veri + 16).to_be_bytes())?;
    } else {
        cikti.write_all(&((toplam_veri + 8) as u32).to_be_bytes())?;
        cikti.write_all(b"mdat")?;
    }
    let mut yazilan: u64 = 0;
    for (iz_no, yigin) in &sira {
        let f = if *iz_no == 0 { &mut vf } else { &mut sf };
        for o in yigin {
            let veri = oku_konum(f, o.ofset, o.boyut)?;
            if veri.len() as u64 != o.boyut {
                return Err(AfuError::Io(
                    "kaynak dosya beklenenden kisa — indirme yarim mi?".into(),
                ));
            }
            cikti.write_all(&veri)?;
            yazilan += o.boyut;
        }
        if let Some(cagri) = ilerleme {
            cagri(yazilan, toplam_veri);
        }
    }
    cikti.flush()?;
    drop(cikti);

    let sure_sn = (video.toplam_sure() as f64 / video.timescale as f64 * 100.0).round() / 100.0;
    Ok(BirlestirOzeti {
        dosya: hedef.to_path_buf(),
        boyut: std::fs::metadata(hedef)?.len(),
        video_ornek: video.ornekler.len(),
        ses_ornek: ses.ornekler.len(),
        sure_sn,
        kodekler: format!("{}+{}", video.kodek, ses.kodek),
    })
}

#[cfg(test)]
mod testler {
    use super::*;

    fn gecici_klasor(ad: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("afudm-mux-{ad}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).expect("test klasoru");
        d
    }

    /// Ornek bir stsd kutusu: `kodek` girisi (codec adi ham[20..24]), gorsel boyut.
    fn stsd_ornek(kodek: &[u8; 4], genislik: u16, yukseklik: u16) -> Vec<u8> {
        let mut govde = vec![0u8; 70];
        govde[24..26].copy_from_slice(&genislik.to_be_bytes());
        govde[26..28].copy_from_slice(&yukseklik.to_be_bytes());
        let giris = kutu(kodek, &[&govde]);
        let mut sd = tam(0).to_vec();
        sd.extend_from_slice(&tam(1));
        sd.extend_from_slice(&giris);
        kutu(b"stsd", &[&sd])
    }

    /// Her ornegi tek yigin olan duz MP4 yazar; veri = ornek icerikleri.
    fn duz_mp4_yaz(
        yol: &Path,
        tur: &str,
        kodek: &[u8; 4],
        timescale: u64,
        sureler: &[u64],
        veri: &[Vec<u8>],
    ) {
        let ornekler: Vec<Ornek> = sureler
            .iter()
            .zip(veri)
            .map(|(&sure, v)| Ornek {
                ofset: 0,
                boyut: v.len() as u64,
                sure,
                cts: 0,
                anahtar: true,
            })
            .collect();
        let (w, h) = if tur == "vide" {
            (640u32, 360u32)
        } else {
            (0, 0)
        };
        let iz = Iz {
            tur: tur.to_string(),
            kodek: String::from_utf8_lossy(kodek).into_owned(),
            timescale,
            stsd_ham: stsd_ornek(kodek, w as u16, h as u16),
            ornekler,
            kaynak: yol.to_path_buf(),
            genislik: w,
            yukseklik: h,
        };
        let yigin_boyut: Vec<usize> = vec![1; veri.len()];
        let ftyp = kutu(b"ftyp", &[b"isom", &tam(0x200)]);
        let mut ofs = vec![0u64; veri.len()];
        let gecici = moov(
            std::slice::from_ref(&iz),
            1000,
            std::slice::from_ref(&ofs),
            std::slice::from_ref(&yigin_boyut),
        );
        let mut konum = (ftyp.len() + gecici.len() + 8) as u64;
        for (i, v) in veri.iter().enumerate() {
            ofs[i] = konum;
            konum += v.len() as u64;
        }
        let moov_bytes = moov(std::slice::from_ref(&iz), 1000, &[ofs], &[yigin_boyut]);
        let mut out = ftyp;
        out.extend_from_slice(&moov_bytes);
        let toplam: usize = veri.iter().map(Vec::len).sum();
        out.extend_from_slice(&((toplam + 8) as u32).to_be_bytes());
        out.extend_from_slice(b"mdat");
        for v in veri {
            out.extend_from_slice(v);
        }
        std::fs::write(yol, out).expect("test mp4 yazimi");
    }

    #[test]
    fn duz_mp4_okunur_ornek_ve_kodek_dogru() {
        let d = gecici_klasor("oku");
        let yol = d.join("v.mp4");
        duz_mp4_yaz(
            &yol,
            "vide",
            b"avc1",
            1000,
            &[500, 500, 500],
            &[vec![1; 10], vec![2; 20], vec![3; 30]],
        );
        let iz = izi_oku(&yol).expect("izi_oku");
        assert_eq!(iz.tur, "vide");
        assert_eq!(iz.kodek, "avc1");
        assert_eq!(iz.ornekler.len(), 3);
        assert_eq!(iz.ornekler[1].boyut, 20);
        assert_eq!((iz.genislik, iz.yukseklik), (640, 360));
        assert_eq!(iz.toplam_sure(), 1500);
    }

    #[test]
    fn birlestir_video_ve_sesi_tek_dosyada_toplar() {
        let d = gecici_klasor("birlestir");
        let v = d.join("video.mp4");
        let s = d.join("ses.m4a");
        duz_mp4_yaz(
            &v,
            "vide",
            b"avc1",
            1000,
            &[500, 500],
            &[vec![7; 16], vec![8; 24]],
        );
        duz_mp4_yaz(&s, "soun", b"mp4a", 1000, &[1000], &[vec![9; 8]]);
        let hedef = d.join("cikti.mp4");
        let ozet = birlestir(&v, &s, &hedef, None).expect("birlestir");
        assert_eq!(ozet.video_ornek, 2);
        assert_eq!(ozet.ses_ornek, 1);
        assert_eq!(ozet.kodekler, "avc1+mp4a");
        assert_eq!(ozet.boyut, std::fs::metadata(&hedef).expect("boyut").len());
        let cikti = izi_oku(&hedef).expect("cikti okunur");
        assert_eq!(cikti.ornekler.len(), 2);
        // Ilk video ornegi cikti dosyasinda ayni baytlari tasimali.
        let bayt = oku_konum(
            &mut File::open(&hedef).expect("ac"),
            cikti.ornekler[0].ofset,
            16,
        )
        .expect("oku");
        assert_eq!(bayt, vec![7u8; 16]);
    }

    #[test]
    fn yiginlar_saniyede_boler() {
        let iz = Iz {
            tur: "vide".into(),
            kodek: "avc1".into(),
            timescale: 1000,
            stsd_ham: vec![],
            ornekler: (0..5)
                .map(|_| Ornek {
                    ofset: 0,
                    boyut: 1,
                    sure: 500,
                    cts: 0,
                    anahtar: true,
                })
                .collect(),
            kaynak: PathBuf::new(),
            genislik: 0,
            yukseklik: 0,
        };
        let y = yiginlar(&iz);
        assert_eq!(y.iter().map(Vec::len).collect::<Vec<_>>(), vec![2, 2, 1]);
    }

    #[test]
    fn ctts_ve_stss_gereksizse_yazilmaz() {
        let duz = vec![Ornek {
            ofset: 0,
            boyut: 1,
            sure: 1,
            cts: 0,
            anahtar: true,
        }];
        assert!(ctts(&duz).is_none());
        assert!(stss(&duz).is_none());
        let b_kare = vec![
            Ornek {
                ofset: 0,
                boyut: 1,
                sure: 1,
                cts: 512,
                anahtar: true,
            },
            Ornek {
                ofset: 1,
                boyut: 1,
                sure: 1,
                cts: -512,
                anahtar: false,
            },
        ];
        assert!(ctts(&b_kare).is_some());
        assert!(stss(&b_kare).is_some());
    }

    /// Gercek ffmpeg ciktilariyla birlestirme (duz ve parcali MP4). Varsayilan olarak atlanir.
    /// AFU_E2E_VIDEO, AFU_E2E_SES, AFU_E2E_CIKTI ortam degiskenleri gerekir.
    #[test]
    #[ignore]
    fn gercek_ffmpeg_dosyalari_birlestirilir() {
        let (Ok(v), Ok(s), Ok(c)) = (
            std::env::var("AFU_E2E_VIDEO"),
            std::env::var("AFU_E2E_SES"),
            std::env::var("AFU_E2E_CIKTI"),
        ) else {
            return;
        };
        let ozet =
            birlestir(Path::new(&v), Path::new(&s), Path::new(&c), None).expect("birlestirilmeli");
        assert_eq!(ozet.kodekler.matches('+').count(), 1);
        assert!(ozet.video_ornek > 0 && ozet.ses_ornek > 0);
    }

    #[test]
    fn bozuk_dosya_hata_verir() {
        let d = gecici_klasor("bozuk");
        let yol = d.join("bos.mp4");
        std::fs::write(&yol, b"bu mp4 degil ama 20 bayt var").expect("yaz");
        assert!(izi_oku(&yol).is_err());
    }
}
