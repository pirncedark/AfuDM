//! Ekler. Bu dosya YALNIZ Claude tarafindan degistirilir.
//! g1 (Ekip G1): guncelleme, reliability, automation, chrome_kurulum
//! g2 (Ekip G2): eklenti + eklenti_host, cerez, linkgrabber, rules
//! h  (Ekip H) : paylasim sunucusu, tunel, smb, mobil esleme
//! Her modul kendi HTTP rotalarini `router(ctx)` ile verir; app hepsini birlestirir.

pub mod g1;
pub mod g2;
pub mod h;

use afudm_types::ApiCtx;

pub fn router(ctx: ApiCtx) -> axum::Router {
    g1::router(ctx.clone()).merge(g2::router(ctx.clone())).merge(h::router(ctx))
}
