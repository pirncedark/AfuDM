//! SAHIBI: Ekip G2. Bu klasordeki her seyi o ekip yazar.

use afudm_types::ApiCtx;

pub fn router(ctx: ApiCtx) -> axum::Router {
    let _ = ctx;
    axum::Router::new()
}
