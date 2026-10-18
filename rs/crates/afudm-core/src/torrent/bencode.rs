//! SAHIBI: Ekip D. Python: tracker_saglik._bencode_oku (HTTP scrape yaniti) ve
//! manager.py _torrent_dosya_infohash (.torrent info hash'i, SHA-1).

use sha1::{Digest, Sha1};
use std::collections::BTreeMap;

/// Python _bencode_oku'daki derinlik siniri.
const DERIN_SINIR: usize = 32;

#[derive(Debug, Clone, PartialEq)]
pub enum Bc {
    Tamsayi(i64),
    Metin(Vec<u8>),
    Liste(Vec<Bc>),
    Sozluk(BTreeMap<Vec<u8>, Bc>),
}

/// Bir degeri `i` konumundan okur; (deger, bitis konumu) doner.
fn oku(veri: &[u8], i: usize, derinlik: usize) -> std::result::Result<(Bc, usize), ()> {
    if i >= veri.len() || derinlik > DERIN_SINIR {
        return Err(());
    }
    match veri[i] {
        b'i' => {
            let son = veri[i + 1..].iter().position(|&c| c == b'e').ok_or(())? + i + 1;
            let metin = std::str::from_utf8(&veri[i + 1..son]).map_err(|_| ())?;
            let sayi: i64 = metin.parse().map_err(|_| ())?;
            Ok((Bc::Tamsayi(sayi), son + 1))
        }
        b'd' => {
            let mut sozluk = BTreeMap::new();
            let mut konum = i + 1;
            while veri.get(konum) != Some(&b'e') {
                let (anahtar, k2) = oku(veri, konum, derinlik + 1)?;
                let Bc::Metin(anahtar) = anahtar else {
                    return Err(());
                };
                let (deger, k3) = oku(veri, k2, derinlik + 1)?;
                sozluk.insert(anahtar, deger);
                konum = k3;
            }
            Ok((Bc::Sozluk(sozluk), konum + 1))
        }
        b'l' => {
            let mut liste = Vec::new();
            let mut konum = i + 1;
            while veri.get(konum) != Some(&b'e') {
                let (deger, k2) = oku(veri, konum, derinlik + 1)?;
                liste.push(deger);
                konum = k2;
            }
            Ok((Bc::Liste(liste), konum + 1))
        }
        c if c.is_ascii_digit() => {
            let iki_nokta = veri[i..].iter().position(|&c| c == b':').ok_or(())? + i;
            let boyut: usize = std::str::from_utf8(&veri[i..iki_nokta])
                .map_err(|_| ())?
                .parse()
                .map_err(|_| ())?;
            let bitis = iki_nokta
                .checked_add(1)
                .and_then(|x| x.checked_add(boyut))
                .ok_or(())?;
            if bitis > veri.len() {
                return Err(());
            }
            Ok((Bc::Metin(veri[iki_nokta + 1..bitis].to_vec()), bitis))
        }
        _ => Err(()),
    }
}

/// Python _bencode_oku: tum veri tek bir degerden olusmali (fazla veri hatadir).
pub fn coz(veri: &[u8]) -> std::result::Result<Bc, ()> {
    let (deger, bitis) = oku(veri, 0, 0)?;
    if bitis != veri.len() {
        return Err(());
    }
    Ok(deger)
}

/// Python _torrent_dosya_infohash: ust sozlukteki "info" degerinin ham SHA-1'i (hex, kucuk harf).
/// Hata ya da bulunamadiysa bos string.
pub fn torrent_info_hash(veri: &[u8]) -> String {
    if !veri.starts_with(b"d") {
        return String::new();
    }
    let mut konum = 1;
    while veri.get(konum) != Some(&b'e') {
        let Ok((anahtar, k2)) = oku(veri, konum, 0) else {
            return String::new();
        };
        let Bc::Metin(anahtar) = anahtar else {
            return String::new();
        };
        let Ok((_, k3)) = oku(veri, k2, 0) else {
            return String::new();
        };
        if anahtar == b"info" {
            return Sha1::digest(&veri[k2..k3])
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect();
        }
        konum = k3;
    }
    String::new()
}

#[cfg(test)]
mod testler {
    use super::*;

    #[test]
    fn sozluk_ve_liste_cozulur() {
        let deger = coz(b"d5:filesd4:abcdd8:completei7eeee").expect("gecerli bencode");
        let Bc::Sozluk(s) = deger else {
            panic!("sozluk bekleniyordu")
        };
        assert!(s.contains_key(&b"files"[..]));
    }

    #[test]
    fn fazla_veri_hatadir() {
        assert!(coz(b"i1ei2e").is_err());
    }

    #[test]
    fn info_hash_info_sozlugunun_sha1i() {
        let info = b"d4:name3:abce";
        let mut torrent = b"d4:info".to_vec();
        torrent.extend_from_slice(info);
        torrent.push(b'e');
        let beklenen: String = Sha1::digest(info)
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect();
        assert_eq!(torrent_info_hash(&torrent), beklenen);
    }

    #[test]
    fn bozuk_torrent_bos_hash_doner() {
        assert_eq!(torrent_info_hash(b"x"), "");
    }
}
