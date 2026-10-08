import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

const src = await readFile(new URL("../extension/download-handoff.js", import.meta.url), "utf8");
const background = await readFile(new URL("../extension/background.js", import.meta.url), "utf8");
const app = await readFile(new URL("../app.py", import.meta.url), "utf8");
const prompt = await readFile(new URL("../ui/download.js", import.meta.url), "utf8");
const context = { setTimeout, clearTimeout };
vm.runInNewContext(src + "\nglobalThis.handoff = AfuDownloadHandoff;", context);
const handle = context.handoff.handle;

function setup({ accepted = true, state = "in_progress" } = {}) {
  const calls = [];
  return {
    calls,
    deps: {
      pause: async (id) => calls.push(["pause", id]),
      eligible: async (_item, url) => { calls.push(["eligible", url]); return true; },
      state: async (id) => { calls.push(["state", id]); return { state, paused: state === "in_progress" }; },
      send: async (_item, url) => { calls.push(["send", url]); return accepted; },
      cancel: async (id) => calls.push(["cancel", id]),
      removeFile: async (id) => calls.push(["removeFile", id]),
      erase: async (id) => calls.push(["erase", id]),
      resume: async (id) => calls.push(["resume", id]),
    },
  };
}

// Regression: a rejected pause must stop Chrome before a slow API request.
const pauseRejected = setup();
pauseRejected.deps.pause = async () => { throw new Error("pause rejected"); };
pauseRejected.deps.send = async () => {
  assert.ok(pauseRejected.calls.some(([name]) => name === "cancel"), "pause rejection cancels Chrome BEFORE send");
  return true;
};
assert.equal(await handle({ id: 101, url: "https://site.test/pause-rejected.pdf" }, pauseRejected.deps), true);
assert.ok(pauseRejected.calls.some(([name]) => name === "erase"));

const pdf = setup();
assert.equal(await handle({ id: 7, url: "https://site.test/open?id=3", finalUrl: "https://cdn.test/report.pdf" }, pdf.deps), true);
assert.ok(pdf.calls.some(([name, value]) => name === "send" && value.endsWith("report.pdf")), "redirected PDF URL is handed off");
assert.ok(pdf.calls.some(([name]) => name === "removeFile"), "accepted Chrome copy is deleted");
assert.ok(pdf.calls.findIndex(([name]) => name === "pause") < pdf.calls.findIndex(([name]) => name === "send"), "Chrome pauses before the handoff request");

const fail = setup({ accepted: false, state: "in_progress" });
assert.equal(await handle({ id: 8, url: "https://site.test/rejected.pdf" }, fail.deps), false);
assert.ok(fail.calls.some(([name]) => name === "resume"), "failed takeover preserves the browser download");
assert.ok(!fail.calls.some(([name]) => name === "removeFile"), "failed takeover never deletes the browser file");

const ineligible = setup();
ineligible.deps.eligible = async () => false;
assert.equal(await handle({ id: 18, url: "https://site.test/skipped.pdf" }, ineligible.deps), false);
assert.ok(ineligible.calls.some(([name]) => name === "resume"), "ineligible paused Chrome download resumes");
const rejected = setup();
rejected.deps.send = async () => { throw new Error("API rejected request"); };
await assert.rejects(handle({ id: 19, url: "https://site.test/rejected.pdf" }, rejected.deps));
assert.ok(rejected.calls.some(([name]) => name === "resume"), "HTTP rejection resumes paused browser download");

const cleanupError = setup({ state: "in_progress" });
cleanupError.deps.cancel = async () => { cleanupError.calls.push(["cancel-failed"]); throw new Error("cancel race"); };
assert.equal(await handle({ id: 13, url: "https://site.test/accepted.pdf" }, cleanupError.deps), true);
assert.ok(!cleanupError.calls.some(([name]) => name === "resume"), "accepted takeover never resumes Chrome after a cancel race");

const completed = setup({ state: "complete" });
assert.equal(await handle({ id: 9, url: "https://site.test/report.pdf" }, completed.deps), true);
assert.ok(completed.calls.some(([name]) => name === "removeFile"), "completed Chrome copy is removed after acceptance");

let releaseSend;
let markReady;
const sendReady = new Promise((resolve) => { markReady = resolve; });
const race = setup();
race.deps.send = async (_item, url) => {
  race.calls.push(["send", url]);
  await new Promise((resolve) => { releaseSend = resolve; markReady(); });
  return true;
};
const first = handle({ id: 10, url: "https://site.test/same.pdf" }, race.deps);
await sendReady;
const second = handle({ id: 11, url: "https://site.test/same.pdf" }, race.deps);
assert.ok(race.calls.some(([name, id]) => name === 'pause' && id === 10), 'Chrome is stopped while send is pending');
releaseSend();
assert.equal(await first, true);
assert.equal(await second, true);
assert.equal(race.calls.filter(([name]) => name === "send").length, 1, "duplicate URL events are handed off once");
assert.ok(race.calls.some(([name, id]) => name === "removeFile" && id === 11), "duplicate browser item is removed after accepted takeover");
assert.equal(await handle({ id: 12, url: "https://site.test/same.pdf" }, race.deps), true);
assert.equal(race.calls.filter(([name]) => name === "send").length, 1, "late duplicate URL event is suppressed briefly");

const timeout = setup();
timeout.deps.timeoutMs = 15;
timeout.deps.send = async () => new Promise(() => {});
await assert.rejects(handle({ id: 90, url: 'https://site.test/timeout.pdf' }, timeout.deps), /timed out/);
assert.ok(timeout.calls.some(([name]) => name === 'resume'), 'timeout resumes Chrome');
assert.ok(!timeout.calls.some(([name]) => name === 'cancel'), 'timeout never cancels Chrome');

const repeated = setup();
await handle({ id: 91, url: 'https://site.test/repeat.pdf' }, repeated.deps);
await handle({ id: 91, url: 'https://site.test/repeat.pdf?redirected' }, repeated.deps);
assert.equal(repeated.calls.filter(([name]) => name === 'send').length, 1, 'same download ID is accepted once');

// Failed early cancellation restarts Chrome, bypassing recursive takeover.
for (const throws of [false, true]) {
  const fallback = setup({ accepted: false });
  const url = `https://site.test/fallback-${throws}.pdf`;
  fallback.deps.pause = async () => { throw new Error("pause rejected"); };
  if (throws) fallback.deps.send = async () => { throw new Error("send failed"); };
  fallback.deps.download = async (_item, restartedUrl) => {
    assert.equal(restartedUrl, url);
    fallback.calls.push(["download", restartedUrl]);
    assert.equal(await handle({ id: 202, url }, fallback.deps), false, "early fallback event bypasses takeover");
    return 202;
  };
  const result = handle({ id: 201, url }, fallback.deps);
  if (throws) await assert.rejects(result, /send failed/);
  else assert.equal(await result, false);
  assert.equal(fallback.calls.filter(([name]) => name === "send").length, throws ? 0 : 1);
  assert.ok(fallback.calls.some(([name]) => name === "download"));
}
const lateFallback = setup({ accepted: false });
lateFallback.deps.pause = async () => { throw new Error("pause rejected"); };
lateFallback.deps.download = async () => 211;
await handle({ id: 210, url: "https://site.test/late-fallback.pdf" }, lateFallback.deps);
assert.equal(await handle({ id: 211, url: "https://cdn.test/redirect.pdf" }, lateFallback.deps), false, "fallback ID bypasses even redirected events");

const slowFallback = setup();
slowFallback.deps.pause = async () => { throw new Error("pause rejected"); };
let releaseSlow;
let readySlow;
const slowReady = new Promise(resolve => { readySlow = resolve; });
slowFallback.deps.send = async () => {
  readySlow();
  return new Promise(resolve => { releaseSlow = resolve; });
};
const slowResult = handle({ id: 220, url: "https://site.test/slow.pdf" }, slowFallback.deps);
await slowReady;
assert.ok(slowFallback.calls.some(([name]) => name === "cancel"), "Chrome canceled before slow send resolves");
releaseSlow(true);
await slowResult;
assert.ok(slowFallback.calls.some(([name]) => name === "erase"));

const completedRace = setup({ state: "complete" });
completedRace.deps.pause = async () => { throw new Error("already complete"); };
completedRace.deps.cancel = async () => { throw new Error("already complete"); };
assert.equal(await handle({ id: 230, url: "https://site.test/complete-race.pdf" }, completedRace.deps), true);
assert.ok(completedRace.calls.some(([name]) => name === "removeFile"), "completed race leaves only AfuDM copy");

const handoff = app.slice(app.indexOf("def tarayicidan_sor"), app.indexOf("def bekleyen_listesi"));
assert.match(handoff, /indirme_penceresi\.goster\(\)/, "browser handoff opens the dedicated prompt");
assert.doesNotMatch(handoff, /one_getir\(self\._window\)/, "browser handoff does not activate the main panel");
assert.match(app, /paths\.UI\s*\/\s*"download\.html"/, "dedicated prompt window loads its own UI");
assert.match(prompt, /bekleyen_onayla/, "download prompt can approve the queued download");
assert.match(prompt, /indirme_durumu/, "download prompt keeps showing live progress after approval");
assert.match(app, /def indirme_durumu\(/, "download window has an isolated progress bridge");

// Exercise the actual service-worker listener without launching a browser window.
const listeners = {};
const event = (name) => ({ addListener(fn) { listeners[name] = fn; } });
let downloadState = "in_progress";
let downloadPaused = false;
let posted = null;
const apiEvents = {
  "downloads.onCreated": event("downloads.onCreated"), "downloads.onChanged": event("downloads.onChanged"),
  "storage.onChanged": event("storage.onChanged"), "webRequest.onBeforeRequest": event("webRequest.onBeforeRequest"),
  "webRequest.onHeadersReceived": event("webRequest.onHeadersReceived"), "tabs.onRemoved": event("tabs.onRemoved"),
  "webNavigation.onCommitted": event("webNavigation.onCommitted"), "runtime.onInstalled": event("runtime.onInstalled"),
  "runtime.onMessage": event("runtime.onMessage"),
  "runtime.onStartup": event("runtime.onStartup"), "alarms.onAlarm": event("alarms.onAlarm"),
  "contextMenus.onInstalled": event("contextMenus.onInstalled"), "contextMenus.onClicked": event("contextMenus.onClicked"),
};
const chromeMock = {
  storage: { local: { get: async (defaults) => ({ ...defaults, port: 6811, token: "local-token", enabled: true, uzantiAcik: true }), set: async () => ({}) },
    session: { get: async () => ({}), set: async () => ({}), remove: async () => ({}) }, onChanged: apiEvents["storage.onChanged"] },
  downloads: {
    onCreated: apiEvents["downloads.onCreated"], onChanged: apiEvents["downloads.onChanged"],
    pause: (_id, cb) => { downloadPaused = true; cb(); },
    resume: (_id, cb) => { downloadPaused = false; chromeMock.resumed = true; cb(); },
    cancel: (_id, cb) => { downloadState = "interrupted"; cb(); },
    removeFile: (_id, cb) => { chromeMock.removed = true; cb(); },
    erase: (_query, cb) => cb(1),
    search: (_query, cb) => cb([{ state: downloadState, paused: downloadPaused }]),
  },
  runtime: { lastError: null, onInstalled: apiEvents["runtime.onInstalled"], onStartup: apiEvents["runtime.onStartup"], onMessage: apiEvents["runtime.onMessage"] },
  cookies: { getAll: async ({ url }) => { chromeMock.cookieUrl = url; return [{ name: "session", value: "secret" }]; } },
  notifications: { create: () => {} }, tabs: { query: async () => [], sendMessage: async () => ({}), onRemoved: apiEvents["tabs.onRemoved"] },
  webRequest: { onBeforeRequest: apiEvents["webRequest.onBeforeRequest"], onHeadersReceived: apiEvents["webRequest.onHeadersReceived"] },
  webNavigation: { onCommitted: apiEvents["webNavigation.onCommitted"] }, alarms: { create: () => {}, clear: () => {}, onAlarm: apiEvents["alarms.onAlarm"] },
  contextMenus: { create: () => {}, onInstalled: apiEvents["contextMenus.onInstalled"], onClicked: apiEvents["contextMenus.onClicked"] },
  i18n: { getMessage: (key) => key },
};
const bgContext = {
  chrome: chromeMock, navigator: { userAgent: "Chrome regression test" }, AbortSignal,
  importScripts: () => {}, setTimeout, clearTimeout,
  fetch: async (url, options = {}) => {
    if (String(url).endsWith("/ping")) return { ok: true };
    posted = JSON.parse(options.body);
    return { ok: true, json: async () => ({ ok: true, pending: true }) };
  },
};
vm.runInNewContext(src + "\nglobalThis.AfuDownloadHandoff = AfuDownloadHandoff;", bgContext);
vm.runInNewContext(background, bgContext);
listeners["downloads.onCreated"]({ id: 42, url: "https://origin.test/preview?id=pdf", finalUrl: "https://files.test/annual-report.pdf", filename: "C:\\Downloads\\annual-report.pdf", referrer: "https://origin.test/", fileSize: 4 * 1024 * 1024 });
for (let i = 0; i < 100 && !chromeMock.removed; i++) await new Promise((resolve) => setTimeout(resolve, 5));
assert.equal(posted?.url, "https://files.test/annual-report.pdf", "final PDF URL crosses the API boundary");
assert.equal(posted?.filename, "annual-report.pdf", "Chrome's PDF filename is retained");
assert.equal(posted?.headers?.Referer, "https://origin.test/", "referrer is forwarded to aria2");
assert.ok(posted?.cookies?.some((cookie) => cookie.name === "session"), "URL-scoped PDF cookies are forwarded");
assert.equal(chromeMock.cookieUrl, "https://files.test/annual-report.pdf", "cookies are selected for the redirected PDF host");
assert.ok(chromeMock.removed, "accepted PDF handoff deletes the Chrome file");

chromeMock.removed = false;
downloadState = "in_progress";
downloadPaused = false;
posted = null;
listeners["downloads.onCreated"]({ id: 43, url: "https://files.test/download?id=annual", finalUrl: "https://files.test/download?id=annual", filename: "", mime: "application/pdf", referrer: "", fileSize: 2 * 1024 * 1024 });
for (let i = 0; i < 100 && !chromeMock.removed; i++) await new Promise((resolve) => setTimeout(resolve, 5));
assert.equal(posted?.filename, "download.pdf", "an inline PDF with an extensionless URL receives a PDF filename");

// Exercise fallback through the actual callback-based Chrome adapter.
chromeMock.downloads.pause = (_id, cb) => {
  chromeMock.runtime.lastError = { message: "pause rejected" };
  cb();
  chromeMock.runtime.lastError = null;
};
let fallbackCount = 0;
chromeMock.downloads.download = (options, cb) => {
  fallbackCount++;
  assert.equal(options.url, "https://files.test/fallback-adapter.pdf");
  listeners["downloads.onCreated"]({ id: 301, url: options.url });
  cb(301);
};
bgContext.fetch = async (url) => {
  if (String(url).endsWith("/ping") || String(url).endsWith("/handoff/error")) return { ok: true };
  throw new Error("send failed");
};
listeners["downloads.onCreated"]({ id: 300, url: "https://files.test/fallback-adapter.pdf", fileSize: 2 * 1024 * 1024 });
for (let i = 0; i < 100 && !fallbackCount; i++) await new Promise(resolve => setTimeout(resolve, 5));
assert.equal(fallbackCount, 1, "failed handoff restarts Chrome once without a takeover loop");

console.log("extension download handoff tests passed");

// Every sender (context menu, media panel and automatic handoff) uses this boundary.
const logged = [];
bgContext.fetch = async (url, options = {}) => {
  if (String(url).endsWith('/ping')) return {ok:true};
  if (String(url).endsWith('/handoff/error')) {
    logged.push(JSON.parse(options.body).error);
    return {ok:true};
  }
  throw new Error('transport failed before download record');
};
await assert.rejects(vm.runInNewContext("sendToAfudm({port:6811,token:'test'}, {url:'https://example.test/pdf'})", bgContext), /transport failed/);
assert.deepEqual(logged, ['transport failed before download record']);

logged.length = 0;
bgContext.fetch = async (url, options = {}) => {
  if (String(url).endsWith('/ping')) return {ok:true};
  if (String(url).endsWith('/handoff/error')) {
    logged.push(JSON.parse(options.body).error);
    return {ok:true};
  }
  return {ok:true, status:200, json:async () => {throw new Error('invalid JSON');}};
};
await assert.rejects(vm.runInNewContext("sendToAfudm({port:6811,token:'test'}, {url:'https://example.test/pdf'})", bgContext));
assert.equal(logged.length, 1, 'malformed acceptance must be logged and must not cancel Chrome');
