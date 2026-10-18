import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const read = (path) => readFile(new URL(path, root), "utf8");
const [background, content, popup, trText, enText] = await Promise.all([
  read("extension/background.js"),
  read("extension/content.js"),
  read("extension/popup.js"),
  read("extension/_locales/tr/messages.json"),
  read("extension/_locales/en/messages.json"),
]);

assert.match(background, /return \{ ok: true, pending: !!sonuc\.pending \};/);
assert.match(background, /reply\(\{ ok: true, result, pending: !!result\.pending \}\);/);

const selectors = [
  content.match(/t\(yanit\.pending \? "([^"]+)" : "([^"]+)"\)/),
  popup.match(/getMessage\(result\.pending \? "([^"]+)" : "([^"]+)"\)/),
];
for (const selector of selectors) {
  assert.ok(selector, "pending/queued message selection exists");
  const [, pendingKey, queuedKey] = selector;
  const messageKey = (pending) => pending ? pendingKey : queuedKey;
  assert.equal(messageKey(true), "msgPending");
  assert.equal(messageKey(false), "msgQueued");
}

const tr = JSON.parse(trText);
const en = JSON.parse(enText);
assert.ok(tr.msgPending.message.length > 0);
assert.ok(en.msgPending.message.length > 0);
console.log("extension pending message tests passed");
