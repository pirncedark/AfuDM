"""Maestro veri siniri guvenlik regresyonlari.

Bu test, MAIN-world yakalayicisini sahte bir pencere ortaminda calistirir.
Beklenen degisiklik: yalnizca indirme izin listesindeki basliklar tasinir ve
kanal nonce/origin denetimi olmadan hicbir liste mesaji yayinlanmaz.
"""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_node(script: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


class MaestroGuvenlikTest(unittest.TestCase):
  def test_hassas_basliklar_maestro_ciktisina_girmez(self):
    """Izin listesinden cikan auth/cookie anahtarlari liste kaydina sizmaz."""
    result = run_node(r'''
      import { readFileSync } from "node:fs";
      import vm from "node:vm";
      const security = readFileSync("extension/maestro-guvenlik.js", "utf8");
      const code = readFileSync("extension/content-maestro.js", "utf8");
      const messages = [];
      const headers = {
        get: (name) => name === "content-type" ? "application/vnd.apple.mpegurl" : null,
        [Symbol.iterator]: function* () {
          yield* Object.entries({
            "content-type": "application/vnd.apple.mpegurl",
            "x-api-key": "secret", authorization: "Bearer secret", cookie: "sid=secret",
            range: "bytes=0-", accept: "*/*", "x-imza": "secret"
          });
        }
      };
      const window = {
        location: { origin: "https://ornek.test" },
        fetch: async () => ({ ok: true, url: "https://ornek.test/a.m3u8", headers,
          clone: () => ({ text: async () => "#EXTM3U" }) }),
        postMessage: (data) => messages.push(data),
        addEventListener(type, fn) { if (type === "message") this.listener = fn; },
        XMLHttpRequest: function () {}, navigator: {}, TextDecoder,
        HTMLMediaElement: function () {}
      };
      window.window = window;
      window.XMLHttpRequest.prototype = {};
      window.HTMLMediaElement.prototype = {};
      const ctx = vm.createContext(window);
      vm.runInContext(security, ctx); vm.runInContext(code, ctx);
      vm.runInContext('listener({ source: window, origin: location.origin, data: { __afudm: "afudm-maestro", tur: "tazele", nonce: "abcdefghijklmnopqrstuvwxyz123456" } })', ctx);
      await window.fetch("https://ornek.test/a.m3u8");
      await new Promise((resolve) => setTimeout(resolve, 10));
      console.log(JSON.stringify(messages.find((m) => m.tur === "liste")));
    ''')
    headers = {key.lower() for key in (result["istek"] | result["yanit"]).keys()}
    self.assertFalse(headers & {"x-api-key", "authorization", "cookie", "x-imza"})
    self.assertTrue({"range", "accept", "content-type"} & headers)


  def test_nonce_ve_origin_yoksa_maestro_mesaji_reddedilir(self):
    """Sahte yenilemeler kanal acamaz; dogru nonce + origin tek kabul yoludur."""
    result = run_node(r'''
      import { readFileSync } from "node:fs";
      import vm from "node:vm";
      const security = readFileSync("extension/maestro-guvenlik.js", "utf8");
      const code = readFileSync("extension/content-maestro.js", "utf8");
      const messages = [];
      const window = {
        location: { origin: "https://ornek.test" }, postMessage: (data) => messages.push(data),
        addEventListener(type, fn) { if (type === "message") this.listener = fn; },
        fetch: async () => ({ ok: true, url: "https://ornek.test/a.m3u8",
          headers: { get: () => "application/vnd.apple.mpegurl", [Symbol.iterator]: function* () {} },
          clone: () => ({ text: async () => "#EXTM3U" }) }),
        XMLHttpRequest: function () {}, navigator: {}, TextDecoder, HTMLMediaElement: function () {}
      };
      window.window = window; window.XMLHttpRequest.prototype = {}; window.HTMLMediaElement.prototype = {};
      const ctx = vm.createContext(window); vm.runInContext(security, ctx); vm.runInContext(code, ctx);
      await window.fetch("https://ornek.test/a.m3u8"); await new Promise((resolve) => setTimeout(resolve, 10));
      messages.length = 0;
      vm.runInContext('listener({ source: window, origin: "https://evil.test", data: { __afudm: "afudm-maestro", tur: "tazele", nonce: "abcdefghijklmnopqrstuvwxyz123456" } })', ctx);
      vm.runInContext('listener({ source: window, origin: location.origin, data: { __afudm: "afudm-maestro", tur: "tazele" } })', ctx);
      console.log(JSON.stringify({ count: messages.length }));
    ''')
    self.assertEqual(result["count"], 0)


if __name__ == "__main__":
    unittest.main()
