import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

// Ikinci yol: AfuDM devraldigi is "error" olursa eklenti dosyayi tarayici
// baglaminda ceker ve /add_blob ile AfuDM'e verir. chrome.downloads kullanmaz.
const handoffSrc = await readFile(new URL("../extension/download-handoff.js", import.meta.url), "utf8");
const background = await readFile(new URL("../extension/background.js", import.meta.url), "utf8");
const MAKS = 512 * 1024 * 1024;

function makeContext() {
  const session = {};
  const notes = [];
  const downloadCalls = [];
  const listeners = {};
  const ev = (name) => ({ addListener(fn) { listeners[name] = fn; } });
  const state = { snapshotItems: [], target: null, posts: [], targetCalls: [], addResponse: { ok: true } };
  const chromeMock = {
    storage: {
      local: {
        get: async (defaults) => ({ ...defaults, port: 6811, token: "tok", enabled: true, uzantiAcik: true,
          downloadContract: 1, skipExtensions: "", minSizeMB: 0 }),
        set: async () => ({}),
      },
      session: {
        get: async (key) => ({ [key]: session[key] }),
        set: async (obj) => { Object.assign(session, obj); },
        remove: async () => ({}),
      },
      onChanged: ev("storage.onChanged"),
    },
    alarms: { create: () => {}, clear: () => {}, onAlarm: ev("alarms.onAlarm") },
    downloads: {
      onCreated: ev("downloads.onCreated"), onChanged: ev("downloads.onChanged"),
      pause: (_id, cb) => cb(),
      resume: (_id, cb) => cb(),
      cancel: (_id, cb) => cb(),
      removeFile: (_id, cb) => cb(),
      erase: (_q, cb) => cb(1),
      search: (_q, cb) => cb([{ state: "in_progress", paused: false }]),
      download: (opts, cb) => { downloadCalls.push(opts); cb(999); },
    },
    runtime: { lastError: null, onInstalled: ev("runtime.onInstalled"), onStartup: ev("runtime.onStartup"), onMessage: ev("runtime.onMessage") },
    cookies: { getAll: async () => [] },
    notifications: { create: (opts) => notes.push(opts.message) },
    tabs: { query: async () => [], sendMessage: async () => ({}), onRemoved: ev("tabs.onRemoved") },
    webRequest: { onBeforeRequest: ev("webRequest.onBeforeRequest"), onHeadersReceived: ev("webRequest.onHeadersReceived") },
    webNavigation: { onCommitted: ev("webNavigation.onCommitted") },
    contextMenus: { create: () => {}, onInstalled: ev("contextMenus.onInstalled"), onClicked: ev("contextMenus.onClicked") },
    i18n: { getMessage: (key) => key, getUILanguage: () => "en" },
  };
  const ctx = {
    URL, Blob, Uint8Array, AbortSignal, setTimeout, clearTimeout, chrome: chromeMock,
    navigator: { userAgent: "test" }, importScripts: () => {},
    fetch: async (url, options = {}) => {
      const u = String(url);
      if (u.endsWith("/ping")) return { ok: true };
      if (u.includes("/snapshot")) return { ok: true, json: async () => ({ items: state.snapshotItems }) };
      if (u.includes("/add_blob")) {
        const body = options.body;
        state.posts.push({ url: u, headers: options.headers, size: body?.size });
        return { ok: true, status: 200, json: async () => ({ ok: true }) };
      }
      if (u.includes("/add")) {
        return { ok: true, status: 200, json: async () => state.addResponse };
      }
      // Hedef adres: tarayici baglami (cerez + referrer ile).
      state.targetCalls.push({ url: u, options });
      const t = state.target || { ok: true, size: 4 };
      return { ok: t.ok !== false, status: t.status || 200, blob: async () => ({ size: t.size ?? 4 }) };
    },
  };
  vm.runInNewContext(handoffSrc + "\nglobalThis.AfuDownloadHandoff = AfuDownloadHandoff;", ctx);
  vm.runInNewContext(background, ctx);
  return { ctx, session, notes, downloadCalls, listeners, state };
}

async function waitFor(check, label) {
  for (let i = 0; i < 200; i++) {
    if (check()) return;
    await new Promise((r) => setTimeout(r, 5));
  }
  assert.fail("timed out waiting for " + label);
}

async function handOff(env, url, filename = "report.zip") {
  env.listeners["downloads.onCreated"]({ id: Math.floor(Math.random() * 1e6), url, referrer: "https://site.test/", filename: "C:\\Downloads\\" + filename, fileSize: 4 });
  await waitFor(() => (env.session.ikinciYolIzleme || []).some((k) => k.url === url), "watch record " + url);
}

const turla = (env) => vm.runInNewContext("ikinciYolTurla()", env.ctx);
const liste = (env) => env.session.ikinciYolIzleme || [];

// 1) AfuDM kabul edince izleme kaydi acilir; Chrome'un kendi indirmesi geri baslatilmaz.
{
  const env = makeContext();
  const url = "https://files.test/report.zip";
  await handOff(env, url);
  assert.equal(env.downloadCalls.length, 0, "accepted handoff never restarts a Chrome download");
  assert.equal(liste(env)[0].referrer, "https://site.test/");
  assert.equal(liste(env)[0].filename, "report.zip");
}

// 2) "error" olunca eklenti dosyayi tarayici baglaminda ceker ve /add_blob ile verir.
{
  const env = makeContext();
  const url = "https://files.test/secure.zip";
  await handOff(env, url);
  env.state.snapshotItems = [{ source: url, status: "error" }];
  env.state.target = { ok: true, size: 1234 };
  await turla(env);
  assert.equal(env.state.targetCalls.length, 1, "target fetched once from the browser context");
  assert.equal(env.state.targetCalls[0].options.credentials, "include", "browser cookies are used");
  assert.equal(env.state.targetCalls[0].options.referrer, "https://site.test/", "referrer is kept");
  assert.equal(env.state.posts.length, 1, "file posted once to /add_blob");
  assert.ok(env.state.posts[0].url.includes("/add_blob?filename=report.zip"));
  assert.equal(env.state.posts[0].headers["X-AfuDM-Token"], "tok");
  assert.equal(env.state.posts[0].size, 1234);
  assert.ok(env.notes.includes("İndirme ikinci yoldan sürüyor."), "user sees the one-line notice");
  assert.equal(liste(env).length, 0, "record is consumed");
  assert.equal(env.downloadCalls.length, 0, "fallback never re-enters chrome.downloads");
  await turla(env);
  assert.equal(env.state.posts.length, 1, "fallback runs only once");
}

// 3) Duraklatilmis ya da indiren is ikinci yolu tetiklemez.
{
  const env = makeContext();
  const url = "https://files.test/paused.zip";
  await handOff(env, url);
  env.state.snapshotItems = [{ source: url, status: "paused" }];
  await turla(env);
  assert.equal(env.state.targetCalls.length, 0, "paused download is not taken over again");
  assert.equal(liste(env).length, 1, "record is kept while paused");
  env.state.snapshotItems = [{ source: url, status: "active" }];
  await turla(env);
  assert.equal(env.state.targetCalls.length, 0, "active download is left alone");
}

// 4) Kullanici sildiyse (gorulup kaybolan) ikinci yol yok.
{
  const env = makeContext();
  const url = "https://files.test/deleted.zip";
  await handOff(env, url);
  env.state.snapshotItems = [{ source: url, status: "active" }];
  await turla(env);
  env.state.snapshotItems = [];
  await turla(env);
  assert.equal(env.state.targetCalls.length, 0, "user-removed download gets no fallback");
  assert.equal(liste(env).length, 0, "record is dropped after removal");
}

// 5) Henuz onay bekleyen (hic gorulmemis) kayit korunur.
{
  const env = makeContext();
  const url = "https://files.test/pending.zip";
  await handOff(env, url);
  env.state.snapshotItems = [];
  await turla(env);
  assert.equal(liste(env).length, 1, "unseen pending approval is kept");
  assert.equal(env.state.targetCalls.length, 0);
}

// 6) Tarayici baglaminda da basarisizsa kullaniciya bildirim; yeniden devir yok.
{
  const env = makeContext();
  const url = "https://files.test/denied.zip";
  await handOff(env, url);
  env.state.snapshotItems = [{ source: url, status: "error" }];
  env.state.target = { ok: false, status: 403 };
  await turla(env);
  assert.equal(env.state.posts.length, 0, "no partial upload after a 403");
  assert.ok(env.notes.includes("İkinci yol da indiremedi; dosyayı tarayıcıdan kaydedin."));
  assert.equal(env.downloadCalls.length, 0, "no chrome.downloads restart");
}

// 7) 512 MB sinirini asan dosya AfuDM'e gonderilmez.
{
  const env = makeContext();
  const url = "https://files.test/huge.iso";
  await handOff(env, url, "huge.iso");
  env.state.snapshotItems = [{ source: url, status: "error" }];
  env.state.target = { ok: true, size: MAKS + 1 };
  await turla(env);
  assert.equal(env.state.posts.length, 0, "oversized file is not posted");
  assert.ok(env.notes.includes("İkinci yol da indiremedi; dosyayı tarayıcıdan kaydedin."));
}

// 8) AfuDM kapaliyken kayit bekler, hic silinmez.
{
  const env = makeContext();
  const url = "https://files.test/offline.zip";
  await handOff(env, url);
  env.ctx.fetch = async () => { throw new Error("connection refused"); };
  await turla(env);
  assert.equal(liste(env).length, 1, "record survives while AfuDM is offline");
}

console.log("extension second-path (ikinci yol) tests passed");
