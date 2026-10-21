import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../extension/background.js", import.meta.url), "utf8");
let sends = 0;
let fail = false;
let now = 1000;
const ctx = vm.createContext({
  Map, URL, Date: { now: () => now }, AbortSignal,
  navigator: { userAgent: "test" },
  cookiesFor: async () => [], ping: async () => true,
  endpoint: () => "http://localhost/add", reportHandoffError: async () => {},
  fetch: async () => {
    ++sends;
    if (fail) throw new Error("offline");
    return { ok: true, json: async () => ({ ok: true, pending: true }) };
  },
});
const start = source.indexOf("const afudmSendActive");
const fallback = source.indexOf("async function sendToAfudm(cfg, body)");
vm.runInContext(source.slice(start < 0 ? fallback : start, source.indexOf("// Page-owned objects")), ctx);
const send = (url) => vm.runInContext(`sendToAfudm({port:6811}, {url:${JSON.stringify(url)}})`, ctx);
await Promise.all(Array.from({ length: 10 }, (_, i) => send(`https://example.com/a#${i}`)));
assert.equal(sends, 1, "concurrent clicks must send one HTTP request");
await send("https://example.com/a");
assert.equal(sends, 1, "recent accepted clicks must send no extra HTTP request");
await send("https://example.com/a?signature=other");
assert.equal(sends, 2, "signed queries stay distinct");
now += 10001;
fail = true;
await assert.rejects(send("https://example.com/a"));
fail = false;
await send("https://example.com/a");
assert.equal(sends, 4, "failed sends must allow retry");
console.log("extension send debounce tests passed");
