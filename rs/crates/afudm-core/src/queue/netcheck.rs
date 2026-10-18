//! Python core/netcheck.py: IPv6 gercekten kullanilabiliyor mu?
//!
//! aria2c IPv6 yolu olmayan makinede AAAA adresini deneyip indirmeyi iptal eder. Olcum
//! UDP "connect" ile yapilir: paket gonderilmez, cekirdek yalnizca rota secer.
//! Sonuc surec omru boyunca onbellekte tutulur (Python _cached ile ayni).
use std::net::{Ipv6Addr, SocketAddr, UdpSocket};
use std::sync::OnceLock;

/// Rota secimi icin kullanilan genel IPv6 adresleri (Google ve Cloudflare DNS).
const PROBE_TARGETS: [&str; 2] = ["[2001:4860:4860::8888]:53", "[2606:4700:4700::1111]:53"];

/// Python _is_global_unicast: 2000::/3 disindaki her sey (loopback, fe80::, fc00::/7) ise yaramaz.
pub(crate) fn global_unicast(ip: &Ipv6Addr) -> bool {
    ip.octets()[0] & 0xE0 == 0x20
}

fn probe() -> bool {
    PROBE_TARGETS.iter().any(|hedef| {
        let Ok(soket) = UdpSocket::bind("[::]:0") else {
            return false;
        };
        if soket.connect(hedef).is_err() {
            return false;
        }
        matches!(soket.local_addr(), Ok(SocketAddr::V6(adres)) if global_unicast(adres.ip()))
    })
}

/// Python ipv6_usable(): sonuc ilk olcumden sonra saklanir.
pub fn ipv6_usable() -> bool {
    static SONUC: OnceLock<bool> = OnceLock::new();
    *SONUC.get_or_init(probe)
}

/// Python aria2_ipv6_args(): IPv6 yoksa aria2'yi IPv4'e kilitle; varsa hicbir sey ekleme.
pub fn aria2_ipv6_args() -> Vec<String> {
    if ipv6_usable() {
        Vec::new()
    } else {
        vec!["--disable-ipv6=true".to_string()]
    }
}

#[cfg(test)]
mod testler {
    use super::*;

    #[test]
    fn yalniz_genel_unicast_yaramali() {
        let genel: Ipv6Addr = "2001:4860:4860::8888".parse().unwrap();
        assert!(global_unicast(&genel));
        for yerel in ["fe80::1", "fd7a:115c:a1e0::1", "::1"] {
            let ip: Ipv6Addr = yerel.parse().unwrap();
            assert!(!global_unicast(&ip), "{yerel} genel sayilmamali");
        }
    }

    #[test]
    fn ipv6_argumani_bilinen_bicimde() {
        let args = aria2_ipv6_args();
        assert!(args.is_empty() || args == ["--disable-ipv6=true"]);
        assert_eq!(args, aria2_ipv6_args(), "onbellek ayni sonucu vermeli");
    }
}
