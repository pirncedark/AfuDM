import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../extension/background.js", import.meta.url), "utf8");
const handler = source.slice(source.indexOf("// Page-owned objects"), source.indexOf("function notify("));

for (const [mime, download, expected] of [
  ["image/jpeg", {}, "download.jpg"],
  ["", {mime: "application/pdf"}, "download.pdf"],
  ["application/unknown", {}, "download.bin"],
  ["image/png", {filename: "folder/cover.webp"}, "cover.webp"],
]) {
  test(expected, async () => {
    let url;
    const ctx = vm.createContext({
      Blob, AbortSignal, endpoint: (_, path) => path,
      fetch: async path => { url = path; return {ok: true, json: async () => ({ok: true})}; },
      chrome: {
        tabs: {query: async () => [{id: 1}], sendMessage: async () => ({ok: true, id: "a", size: 0, mime})},
        webNavigation: {getAllFrames: async () => [{frameId: 0}]},
      },
    });
    const send = vm.runInContext(handler + "\nsendLocalFile", ctx);
    await send({}, download, "blob:https://example.test/id");
    assert.equal(url, "/add_blob?filename=" + expected);
  });
}
