//! Python core/db.py schema versions 1 through 10, without new migrations.
use rusqlite::Connection;
pub(crate) const BASE: &str = r#"
CREATE TABLE IF NOT EXISTS downloads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    gid         TEXT UNIQUE,
    kind        TEXT NOT NULL DEFAULT 'http',
    source      TEXT NOT NULL,
    title       TEXT,
    dest_dir    TEXT,
    filename    TEXT,
    total_bytes INTEGER DEFAULT 0,
    done_bytes  INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'queued',
    error       TEXT,
    options     TEXT DEFAULT '{}',
    added_at    REAL NOT NULL,
    started_at  REAL,
    finished_at REAL,
    start_after REAL
);
CREATE INDEX IF NOT EXISTS idx_downloads_status ON downloads(status);
CREATE INDEX IF NOT EXISTS idx_downloads_gid    ON downloads(gid);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    at       REAL NOT NULL,
    level    TEXT NOT NULL,
    message  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS automation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    download_gid TEXT NOT NULL,
    action TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    attempt INTEGER NOT NULL DEFAULT 0,
    progress INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    finished_at REAL,
    UNIQUE(download_gid, action)
);
CREATE INDEX IF NOT EXISTS idx_automation_jobs_status ON automation_jobs(status, id);
"#;
const V2: &str = r#"
        CREATE TABLE IF NOT EXISTS torrent_file_selections (
            gid        TEXT NOT NULL,
            file_index INTEGER NOT NULL,
            selected   INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (gid, file_index)
        )
    ;"#;
const V4: &str = r#"
    CREATE TABLE IF NOT EXISTS automation_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, download_gid TEXT NOT NULL,
        action TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'queued', attempt INTEGER NOT NULL DEFAULT 0,
        progress INTEGER NOT NULL DEFAULT 0, error TEXT, created_at REAL NOT NULL,
        started_at REAL, finished_at REAL, UNIQUE(download_gid, action)
    );
    CREATE INDEX IF NOT EXISTS idx_automation_jobs_status ON automation_jobs(status, id);
    ;"#;
const V5: &str = r#"CREATE TABLE IF NOT EXISTS mobile_devices (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'owner',
        token_hash TEXT NOT NULL, created_at REAL NOT NULL, last_seen REAL NOT NULL,
        revoked_at REAL
    );"#;
const V7: &str = r#"CREATE TABLE IF NOT EXISTS rules (id TEXT PRIMARY KEY,name TEXT NOT NULL,active INTEGER DEFAULT 1,priority INTEGER NOT NULL,match_type TEXT NOT NULL,conditions TEXT NOT NULL,actions TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_rules_priority ON rules(priority);"#;
const V8: &str = r#"
        CREATE TABLE IF NOT EXISTS plugins (
            ad            TEXT PRIMARY KEY,
            baslik        TEXT NOT NULL DEFAULT '',
            surum         TEXT NOT NULL DEFAULT '',
            kaynak        TEXT NOT NULL DEFAULT '',
            giris         TEXT NOT NULL DEFAULT '',
            manifest      TEXT NOT NULL DEFAULT '{}',
            izinler       TEXT NOT NULL DEFAULT '[]',
            domainler     TEXT NOT NULL DEFAULT '[]',
            ayarlar       TEXT NOT NULL DEFAULT '{}',
            etkin         INTEGER NOT NULL DEFAULT 0,
            son_hata      TEXT NOT NULL DEFAULT '',
            onceki_surum  TEXT NOT NULL DEFAULT '',
            kurulum_at    REAL NOT NULL DEFAULT 0,
            guncelleme_at REAL NOT NULL DEFAULT 0
        )
    ;"#;
const V9: &str = r#"
        CREATE TABLE IF NOT EXISTS api_keys (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ad          TEXT NOT NULL,
            rol         TEXT NOT NULL DEFAULT 'salt_okur',
            gizli_hash  TEXT NOT NULL,
            onek        TEXT NOT NULL DEFAULT '',
            olusturuldu REAL NOT NULL,
            son_kullanim REAL,
            son_rotasyon REAL,
            iptal       INTEGER NOT NULL DEFAULT 0,
            not_metni   TEXT DEFAULT ''
        )
    ;
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(gizli_hash);

        CREATE TABLE IF NOT EXISTS api_clients (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id       INTEGER,
            oturum       TEXT NOT NULL UNIQUE,
            ip           TEXT NOT NULL DEFAULT '',
            istemci      TEXT NOT NULL DEFAULT '',
            rol          TEXT NOT NULL DEFAULT 'salt_okur',
            ilk_gorulme  REAL NOT NULL,
            son_gorulme  REAL NOT NULL,
            istek_sayisi INTEGER NOT NULL DEFAULT 0,
            iptal        INTEGER NOT NULL DEFAULT 0
        )
    ;
CREATE INDEX IF NOT EXISTS idx_api_clients_oturum ON api_clients(oturum);

        CREATE TABLE IF NOT EXISTS server_profiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ad          TEXT NOT NULL,
            adres       TEXT NOT NULL DEFAULT 'yerel',
            port        INTEGER NOT NULL DEFAULT 6821,
            originler   TEXT NOT NULL DEFAULT '',
            istek_limiti INTEGER NOT NULL DEFAULT 120,
            olusturuldu REAL NOT NULL
        )
    ;"#;
pub(crate) fn migrate(conn: &mut Connection) -> rusqlite::Result<()> {
    let version: i64 = conn.query_row("PRAGMA user_version", [], |r| r.get(0))?;
    let tx = conn.transaction()?;
    for v in (version + 1)..=10 {
        match v {
            2 => tx.execute_batch(V2)?,
            3 => add_column(&tx, "events", "gid", "TEXT")?,
            4 => tx.execute_batch(V4)?,
            5 => tx.execute_batch(V5)?,
            6 => {
                tx.execute_batch(V4)?;
                tx.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('api_listen_port',COALESCE((SELECT NULLIF(value,'') FROM settings WHERE key='api_port'),'6811'))", [])?;
            }
            7 => tx.execute_batch(V7)?,
            8 => tx.execute_batch(V8)?,
            9 => tx.execute_batch(V9)?,
            10 => add_column(&tx, "plugins", "sha256", "TEXT NOT NULL DEFAULT ''")?,
            _ => {}
        }
        tx.pragma_update(None, "user_version", v)?;
    }
    tx.commit()
}
fn add_column(conn: &Connection, table: &str, name: &str, ty: &str) -> rusqlite::Result<()> {
    let mut stmt = conn.prepare(&format!("PRAGMA table_info({table})"))?;
    let names = stmt
        .query_map([], |r| r.get::<_, String>(1))?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    if !names.iter().any(|n| n == name) {
        conn.execute_batch(&format!("ALTER TABLE {table} ADD COLUMN {name} {ty}"))?;
    }
    Ok(())
}
