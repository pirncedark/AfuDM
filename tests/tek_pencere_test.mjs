import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../rs/app/ui/app.js", import.meta.url), "utf8");
const elements = new Map();
const get = (id) => {
  if (!elements.has(id)) elements.set(id, { value: "", style: {}, focus() {}, classList: { contains: () => false } });
  return elements.get(id);
};
const context = vm.createContext({
  $: get, kayit: {}, torState: { dosyalar: [] }, state: { settings: {} },
  call: async () => ({ kind: "http", ana: "F:/downloads" }),
  kategoriDoldur() {}, kayHedefYaz() {}, openVeil() {},
  kayAciliyor: false, kayKapatiliyor: false, kaySira: 0,
});
// Execute the real dialog opener, with only its DOM and bridge boundaries stubbed.
const start = source.indexOf("async function kaydetAc(istek)");
const end = source.indexOf('$("kayCat").onchange', start);
vm.runInContext(source.slice(start, end), context);
await vm.runInContext('kaydetAc({kimlik: 42, url: "magnet:?xt=test", kind: "http"})', context);
assert.equal(context.kayit.kimlik, 42, "Rust request identity must survive opening and reach approval/cancel");
console.log("tek pencere: request identity passed");

let opened = false;
let dialogs = 0;
context.openVeil = () => { opened = true; ++dialogs; };
get("kaydetVeil").classList.contains = () => opened;
await Promise.all(Array.from({ length: 10 }, () =>
  vm.runInContext('kaydetAc({kimlik: 43, url: "magnet:?xt=test", kind: "http"})', context)));
assert.equal(dialogs, 1, "simultaneous requests must open only one dialog");

const pollStart = source.indexOf("async function bekleyenYokla()");
const pollEnd = source.indexOf("window.afudmBekleyen =", pollStart);
context.bekleyenMesgul = false;
context.window = { afudmMevcut: async () => {} };
context.t = (_key, {n}) => String(n);
context.toast = (error) => { throw new Error(error); };
vm.runInContext(source.slice(pollStart, pollEnd), context);
context.call = async () => ({ ogeler: [{kimlik:43}, {kimlik:44}] });
await vm.runInContext("bekleyenYokla()", context);
assert.equal(dialogs, 1, "an already open dialog must only update its counter");
assert.equal(get("kayQueue").textContent, "1");

opened = false;
let finishList;
let polls = 0;
context.call = () => { ++polls; return new Promise(resolve => { finishList = resolve; }); };
const poll = vm.runInContext("bekleyenYokla()", context);
await vm.runInContext("bekleyenYokla()", context);
assert.equal(polls, 1, "overlapping polls must not race to open the same request");
context.kaySira += 1; // User closed/cancelled while the old list was in flight.
finishList({ogeler:[{kimlik:43}]});
await poll;
assert.equal(dialogs, 1, "a stale response must not reopen a cancelled request");
console.log("tek pencere: concurrent open, counter and stale-cancel tests passed");
