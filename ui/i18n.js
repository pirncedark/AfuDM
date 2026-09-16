/* AfuDM dil katmani — Turkce ve Ingilizce.
 *
 * Kullanim:
 *   t("bar.add")                 -> "Link ekle" / "Add link"
 *   t("toast.cleared", {n: 3})   -> "3 kayit temizlendi" / "3 entries cleared"
 *   applyStatic()                -> HTML'deki data-i18n islaretli her seyi yazar
 *
 * HTML tarafinda uc nitelik okunur:
 *   data-i18n="anahtar"        -> dugumun metni
 *   data-i18n-ph="anahtar"     -> placeholder
 *   data-i18n-title="anahtar"  -> title (fare ustune gelince)
 *
 * Dil secimi Python tarafindan gelir (ayar: auto | tr | en). "auto" ise
 * Windows arayuz dili kullanilir — karar core/lang.py'de verilir, burasi
 * yalnizca gelen kodu uygular.
 */

const DICT = {
  tr: {
    "app.title": "AfuDM — indirme yöneticisi",

    "trace.unit": "MB/s indirme",
    "trace.active": "aktif",
    "trace.queued": "kuyrukta",
    "trace.share": "paylaşım",
    "trace.today": "bugün",

    "engine.connecting": "motor bağlanıyor",
    "engine.running": "aria2 çalışıyor",
    "engine.stopped": "motor kapalı",
    "engine.offline": "bağlantı yok",

    "filter.all": "Tümü",
    "filter.active": "İndiriliyor",
    "filter.paused": "Duraklatıldı",
    "filter.video": "Video",
    "filter.torrent": "Torrent",
    "filter.complete": "Bitti",
    "filter.error": "Hata",

    "rail.openFolder": "İndirme klasörünü aç",
    "rail.settings": "Ayarlar",

    "bar.add": "Link ekle",
    "bar.pauseAll": "Tümünü duraklat",
    "bar.resumeAll": "Tümünü sürdür",
    "bar.search": "listede ara",
    "bar.clearDone": "Bitenleri temizle",

    "empty.title": "Kuyruk boş.",
    "empty.hint": "Link ekleyip başla — dosya, video veya magnet.",

    "state.active": "indiriliyor",
    "state.waiting": "kuyrukta",
    "state.paused": "duraklatıldı",
    "state.complete": "bitti",
    "state.error": "hata",
    "state.removed": "kaldırıldı",
    "state.scheduled": "zamanlandı",
    "state.queued": "kuyrukta",
    "state.seeding": "paylaşılıyor",

    "row.pause": "Duraklat",
    "row.resume": "Sürdür",
    "row.remove": "Kaldır",
    "row.folder": "Klasör",
    "row.delete": "Sil",
    "row.retry": "Yeniden dene",
    "row.conn": "bağlantı",
    "row.seed": "seed",

    "kv.status": "Durum",
    "kv.size": "Boyut",
    "kv.downloaded": "İnen",
    "kv.speed": "Hız",
    "kv.eta": "Kalan süre",
    "kv.conn": "Bağlantı",
    "kv.seed": "Seed",
    "kv.sent": "Gönderilen",
    "kv.upspeed": "Paylaşım hızı",
    "kv.ratio": "Oran",
    "kv.infohash": "Info hash",
    "kv.folder": "Klasör",
    "kv.file": "Dosya",
    "kv.error": "Hata",
    "kv.unknown": "bilinmiyor",

    "peers.addr": "Adres",
    "peers.type": "Tür",
    "peers.down": "İnen",
    "peers.up": "Giden",
    "peers.client": "İstemci",

    "drawer.close": "Kapat",

    "add.title": "Link ekle",
    "add.urls": "Bağlantı (her satıra bir tane — http, magnet veya video sayfası)",
    "add.quality": "Video kalitesi",
    "add.q.best": "En iyi",
    "add.q.2160": "4K'ya kadar",
    "add.q.1080": "1080p'ye kadar",
    "add.q.720": "720p'ye kadar",
    "add.q.480": "480p'ye kadar",
    "add.q.audio": "Sadece ses (mp3)",
    "add.startAt": "Saatinde başlat (boş = hemen)",
    "add.playlist": "Playlist'in tamamını al",
    "add.audioOnly": "Sesi mp3 olarak çıkar",
    "add.dest": "Hedef klasör (boş = varsayılan)",
    "add.cancel": "Vazgeç",
    "add.go": "İndirmeye başla",

    "set.title": "Ayarlar",
    "set.lang": "Dil / Language",
    "set.lang.auto": "Otomatik (Windows dili)",
    "set.lang.tr": "Türkçe",
    "set.lang.en": "English",
    "set.engines": "Motorlar",
    "set.enginesHint": "Küçük paket için video motorları ayrı iniyor. İndirdiklerin uygulama klasöründe kalır.",
    "eng.installed": "kurulu",
    "eng.fromSystem": "sistemden",
    "eng.fromSystemTip": "Bu motor uygulama klasöründe değil, Windows'ta kurulu olandan kullanılıyor. Sürümü bizim denetimimizde değil; başka bilgisayarda çalışmayabilir. İndirirsen kendi kopyan olur.",
    "eng.required": "zorunlu",
    "eng.download": "İndir ({mb} MB)",
    "eng.downloading": "iniyor… %{yuzde}",
    "eng.done": "indirildi",
    "eng.failed": "indirilemedi",
    "eng.aria2c": "İndirme motoru",
    "eng.yt-dlp": "Video siteleri (YouTube, Instagram, TikTok…)",
    "eng.ffmpeg": "1080p ve üstü birleştirme + mp3",
    "set.dir": "İndirme klasörü",
    "set.dirHint": "Boş bırakırsan uygulama klasöründeki downloads kullanılır (portable).",
    "set.split": "Dosya başına parça (split)",
    "set.conn": "Sunucu başına bağlantı",
    "set.conc": "Aynı anda indirme",
    "set.speed": "Hız sınırı (KB/s, 0 = sınırsız)",
    "set.ratio": "Seed oranı (torrent)",
    "set.chat": "Telegram sohbet kimliği",
    "set.token": "Telegram bot anahtarı (bildirim için)",
    "set.clip": "Panoya kopyalanan linki yakala",
    "set.trackers": "Tracker listesini günlük güncelle",
    "set.notify": "Bitince Telegram'a haber ver",
    "set.shutdown": "Hepsi bitince bilgisayarı kapat",
    "set.pair": "Uzantıyı bağla",
    "set.cancel": "Vazgeç",
    "set.save": "Ayarları kaydet",

    "toast.retried": "Yeniden başlatıldı",
    "toast.cleared": "{n} kayıt temizlendi",
    "toast.started": "{n} indirme başlatıldı",
    "toast.scheduled": "{n} indirme zamanlandı",
    "toast.failed": ", {n} başarısız",
    "toast.saved": "Ayarlar kaydedildi",
    "toast.pairing": "2 dakika boyunca uzantıdan 'Otomatik bağlan' diyebilirsin (port {port}).",
    "toast.clipboard": "Panodan link alındı.",

    "err.noLink": "En az bir bağlantı gir.",
    "err.bridge": "köprü hazır değil",
    "err.failed": "işlem başarısız",
    "err.noRetry": "bu kayıt yeniden başlatılamıyor",
    "hint.api": "Tarayıcı uzantısı bağlantısı: 127.0.0.1:{port} — anahtar data/api_endpoint.json içinde.",
  },

  en: {
    "app.title": "AfuDM — download manager",

    "trace.unit": "MB/s download",
    "trace.active": "active",
    "trace.queued": "queued",
    "trace.share": "upload",
    "trace.today": "today",

    "engine.connecting": "connecting to engine",
    "engine.running": "aria2 running",
    "engine.stopped": "engine stopped",
    "engine.offline": "no connection",

    "filter.all": "All",
    "filter.active": "Downloading",
    "filter.paused": "Paused",
    "filter.video": "Video",
    "filter.torrent": "Torrent",
    "filter.complete": "Finished",
    "filter.error": "Failed",

    "rail.openFolder": "Open download folder",
    "rail.settings": "Settings",

    "bar.add": "Add link",
    "bar.pauseAll": "Pause all",
    "bar.resumeAll": "Resume all",
    "bar.search": "search the list",
    "bar.clearDone": "Clear finished",

    "empty.title": "The queue is empty.",
    "empty.hint": "Add a link to start — a file, a video or a magnet.",

    "state.active": "downloading",
    "state.waiting": "queued",
    "state.paused": "paused",
    "state.complete": "finished",
    "state.error": "failed",
    "state.removed": "removed",
    "state.scheduled": "scheduled",
    "state.queued": "queued",
    "state.seeding": "seeding",

    "row.pause": "Pause",
    "row.resume": "Resume",
    "row.remove": "Remove",
    "row.folder": "Folder",
    "row.delete": "Delete",
    "row.retry": "Try again",
    "row.conn": "connections",
    "row.seed": "seeds",

    "kv.status": "Status",
    "kv.size": "Size",
    "kv.downloaded": "Downloaded",
    "kv.speed": "Speed",
    "kv.eta": "Time left",
    "kv.conn": "Connections",
    "kv.seed": "Seeds",
    "kv.sent": "Uploaded",
    "kv.upspeed": "Upload speed",
    "kv.ratio": "Ratio",
    "kv.infohash": "Info hash",
    "kv.folder": "Folder",
    "kv.file": "File",
    "kv.error": "Error",
    "kv.unknown": "unknown",

    "peers.addr": "Address",
    "peers.type": "Type",
    "peers.down": "Down",
    "peers.up": "Up",
    "peers.client": "Client",

    "drawer.close": "Close",

    "add.title": "Add link",
    "add.urls": "Link (one per line — http, magnet or a video page)",
    "add.quality": "Video quality",
    "add.q.best": "Best",
    "add.q.2160": "up to 4K",
    "add.q.1080": "up to 1080p",
    "add.q.720": "up to 720p",
    "add.q.480": "up to 480p",
    "add.q.audio": "Audio only (mp3)",
    "add.startAt": "Start at (empty = now)",
    "add.playlist": "Grab the whole playlist",
    "add.audioOnly": "Extract audio as mp3",
    "add.dest": "Target folder (empty = default)",
    "add.cancel": "Cancel",
    "add.go": "Start download",

    "set.title": "Settings",
    "set.lang": "Dil / Language",
    "set.lang.auto": "Automatic (Windows language)",
    "set.lang.tr": "Türkçe",
    "set.lang.en": "English",
    "set.engines": "Engines",
    "set.enginesHint": "To keep the package small, video engines are downloaded separately. What you download stays in the app folder.",
    "eng.installed": "installed",
    "eng.fromSystem": "from system",
    "eng.fromSystemTip": "This engine is not in the app folder; the one installed on Windows is used. Its version is not under our control and it may be missing on another machine. Download it to get your own copy.",
    "eng.required": "required",
    "eng.download": "Download ({mb} MB)",
    "eng.downloading": "downloading… {yuzde}%",
    "eng.done": "downloaded",
    "eng.failed": "download failed",
    "eng.aria2c": "Download engine",
    "eng.yt-dlp": "Video sites (YouTube, Instagram, TikTok…)",
    "eng.ffmpeg": "1080p+ merging and mp3",
    "set.dir": "Download folder",
    "set.dirHint": "Leave empty to use the downloads folder inside the app directory (portable).",
    "set.split": "Pieces per file (split)",
    "set.conn": "Connections per server",
    "set.conc": "Simultaneous downloads",
    "set.speed": "Speed limit (KB/s, 0 = unlimited)",
    "set.ratio": "Seed ratio (torrent)",
    "set.chat": "Telegram chat id",
    "set.token": "Telegram bot token (for notifications)",
    "set.clip": "Catch links copied to the clipboard",
    "set.trackers": "Update the tracker list daily",
    "set.notify": "Notify Telegram when finished",
    "set.shutdown": "Shut down the computer when all are done",
    "set.pair": "Pair the extension",
    "set.cancel": "Cancel",
    "set.save": "Save settings",

    "toast.retried": "Restarted",
    "toast.cleared": "{n} entries cleared",
    "toast.started": "{n} downloads started",
    "toast.scheduled": "{n} downloads scheduled",
    "toast.failed": ", {n} failed",
    "toast.saved": "Settings saved",
    "toast.pairing": "For the next 2 minutes you can hit 'Auto connect' in the extension (port {port}).",
    "toast.clipboard": "Link taken from the clipboard.",

    "err.noLink": "Enter at least one link.",
    "err.bridge": "bridge not ready",
    "err.failed": "the operation failed",
    "err.noRetry": "this entry cannot be restarted",
    "hint.api": "Browser extension endpoint: 127.0.0.1:{port} — the key is in data/api_endpoint.json.",
  },
};

let LANG = "tr";

function setLang(code) {
  LANG = DICT[code] ? code : "tr";
  document.documentElement.lang = LANG;
}

function currentLang() {
  return LANG;
}

function t(key, vars) {
  const table = DICT[LANG] || DICT.tr;
  let text = table[key];
  if (text === undefined) text = (DICT.tr[key] !== undefined ? DICT.tr[key] : key);
  if (vars) {
    for (const name in vars) {
      text = text.split("{" + name + "}").join(String(vars[name]));
    }
  }
  return text;
}

/* HTML'deki isaretli dugumleri mevcut dile gore yeniden yazar. */
function applyStatic(root) {
  const scope = root || document;
  scope.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.getAttribute("data-i18n"));
  });
  scope.querySelectorAll("[data-i18n-ph]").forEach((node) => {
    node.placeholder = t(node.getAttribute("data-i18n-ph"));
  });
  scope.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.title = t(node.getAttribute("data-i18n-title"));
  });
  document.title = "AfuDM";
}
