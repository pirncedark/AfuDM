import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import test from "node:test";

const source = await readFile(new URL("../extension/background.js", import.meta.url), "utf8");
const section = source.slice(source.indexOf("const IKINCI_YOL_ALARMI"), source.indexOf("/* --- 1) Tarayici"));
function fixture(saved = {}) {
  const calls = [];
  const cfg = { enabled: true, uzantiAcik: true, token: "test-token", port: 9999 };
  let response = { ok: true, json: async () => ({ items: [] }) };
  const context = vm.createContext({ URL, AbortSignal, Blob, Date,
    chrome: { storage: { session: {
      get: async () => structuredClone(saved),
      set: async (value) => Object.assign(saved, structuredClone(value)),
    } }, alarms: { create: (...args) => calls.push(["alarm", ...args]), clear: () => {} } },
    config: async () => cfg, endpoint: (_, path) => "http://127.0.0.1:9999" + path,
    fetch: async (...args) => { calls.push(["fetch", ...args]); return response; },
    notify: () => {}, ping: async () => true, portTara: async () => {},
  });
  vm.runInContext(section, context);
  return { saved, calls, cfg, run: (code) => vm.runInContext(code, context),
    respond: (value) => { response = value; },
    items: (items) => { response = { ok: true, json: async () => ({ items }) }; } };
}
const url = "https://files.test/report.pdf";
async function track(f) {
  await f.run(`ikinciYolEkle(${JSON.stringify(url)}, "https://site.test/", ${JSON.stringify(String.raw`C:\Downloads\report.pdf`)})`);
}

test("concurrent registrations survive service worker reload", async () => {
  const f = fixture();
  await Promise.all([track(f), f.run('ikinciYolEkle("https://files.test/b.zip", "", "")')]);
  assert.equal(f.saved.ikinciYolIzleme.length, 2);
  assert.equal(f.saved.ikinciYolIzleme[0].filename, "report.pdf");
  const reloaded = fixture(f.saved);
  reloaded.items([{source: url, status: "error"}]);
  assert.equal((await reloaded.run("ikinciYolKontrol()")).indirilecek.length, 1);
});
for (const status of ["active", "paused", "waiting", "complete", "removed", "error"]) {
  test(`only error triggers fallback: ${status}`, async () => {
    const f = fixture(); await track(f); f.items([{ source: url, status }]);
    const result = await f.run("ikinciYolKontrol()");
    assert.equal(result.indirilecek.length, status === "error" ? 1 : 0);
  });
}
test("removed observed job is forgotten", async () => {
  const f = fixture(); await track(f); f.items([{ source: url, status: "active" }]);
  await f.run("ikinciYolKontrol()"); f.items([]); await f.run("ikinciYolKontrol()");
  assert.equal(f.saved.ikinciYolIzleme.length, 0);
});
test("failed snapshot response preserves tracked job", async () => {
  const f = fixture(); await track(f); f.saved.ikinciYolIzleme[0].goruldu = true;
  f.respond({ ok: false, json: async () => ({ error: "offline" }) });
  assert.equal((await f.run("ikinciYolKontrol()")).indirilecek.length, 0);
  assert.equal(f.saved.ikinciYolIzleme.length, 1);
});
test("disabled extension does not start fallback", async () => {
  const f = fixture(); await track(f); f.cfg.uzantiAcik = false;
  f.items([{ source: url, status: "error" }]);
  assert.equal((await f.run("ikinciYolKontrol()")).indirilecek.length, 0);
});
test("browser fetch uploads a binary blob with token and safe filename", async () => {
  const f = fixture(); await track(f);
  f.respond({ ok: true, blob: async () => new Blob(["pdf-body"]), json: async () => ({ ok: true }) });
  await f.run(`ikinciYolIndir({token:"test-token",port:9999}, ${JSON.stringify(f.saved.ikinciYolIzleme[0])})`);
  const requests = f.calls.filter(([kind]) => kind === "fetch");
  assert.equal(requests[0][2].credentials, "include");
  assert.equal(requests[0][2].referrer, "https://site.test/");
  assert.match(requests[1][1], /\/add_blob\?filename=report.pdf$/);
  assert.equal(requests[1][2].headers["X-AfuDM-Token"], "test-token");
  assert.equal(await requests[1][2].body.text(), "pdf-body");
});

test("malformed snapshot preserves observed jobs", async () => {
  const f = fixture(); await track(f); f.saved.ikinciYolIzleme[0].goruldu = true;
  f.respond({ ok: true, json: async () => ({ items: {} }) });
  assert.equal((await f.run("ikinciYolKontrol()")).indirilecek.length, 0);
  assert.equal(f.saved.ikinciYolIzleme.length, 1);
});
test("expired jobs never trigger fallback", async () => {
  const f = fixture(); await track(f);
  f.saved.ikinciYolIzleme[0].ts = Date.now() - 25 * 60 * 60 * 1000;
  f.items([{ source: url, status: "error" }]);
  assert.equal((await f.run("ikinciYolKontrol()")).indirilecek.length, 0);
  assert.equal(f.saved.ikinciYolIzleme.length, 0);
});
test("an error is handed off only once across alarm ticks", async () => {
  const f = fixture(); await track(f); f.items([{ source: url, status: "error" }]);
  assert.equal((await f.run("ikinciYolKontrol()")).indirilecek.length, 1);
  assert.equal((await f.run("ikinciYolKontrol()")).indirilecek.length, 0);
});
