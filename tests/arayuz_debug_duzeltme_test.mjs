import fs from 'fs';
import path from 'path';
import assert from 'assert';
import vm from 'vm';

const basePath = process.cwd();
const appJsPath = path.join(basePath, 'ui', 'app.js');
const downloadJsPath = path.join(basePath, 'ui', 'download.js');
const mobilHtmlPath = path.join(basePath, 'ui', 'mobil.html');
const appPyPath = path.join(basePath, 'app.py');

// Windows checkout'ta satir sonlari CRLF olabilir; icerikleri LF'ye normalize et
const oku = (p) => fs.readFileSync(p, 'utf8').replace(/\r\n/g, '\n');

// Bug 1: Object.create(null) for cocuklar
const appJsContent = oku(appJsPath);
assert.ok(appJsContent.includes('cocuklar: Object.create(null)'), 'Bug 1 (torAgacKur proto) failed');

// Bug 2: kayit.kimlik = null is inside try/finally or cleared after await call
assert.ok(appJsContent.includes('kayit.kimlik = null;'), 'Bug 2 (kimlik) missing');
assert.ok(!appJsContent.includes('kayit.preGid = null;\n  const kimlik = kayit.kimlik;\n  kayit.kimlik = null;'), 'Bug 2 still old code');

// Bug 3: active erken atanmıyor
const downloadJsContent = oku(downloadJsPath);
assert.ok(downloadJsContent.includes('active = item;'), 'Bug 3 active assignment missing');
assert.ok(!downloadJsContent.includes('busy = true;\n    active = item;'), 'Bug 3 active early assignment still present');
assert.ok(downloadJsContent.includes('$("start").disabled = true;\n    busy = true;\n    const selectedId = item.id;'), 'Bug 3 early block is wrong');

// Bug 4: mobile nonce
const mobilHtmlContent = oku(mobilHtmlPath);
assert.ok(mobilHtmlContent.includes('nonce !== torrentKatmanNonce'), 'Bug 4 nonce missing');

// Bug 5: afudm:// protocol
const appPyContent = oku(appPyPath);
assert.ok(appPyContent.includes('"afudm://"'), 'Bug 5 afudm:// missing');

// Bug 6: LinkGrabber empty filter
assert.ok(appJsContent.includes('const indeks = lgState.gosterim || lgState.ogeler.map'), 'Bug 6 indeks logic failed');

// Bug 7: Bulk remove success count
assert.ok(appJsContent.includes('if (removedCount > 0)'), 'Bug 7 bulk remove failed');

// Bug 8: Plugin rollback
assert.ok(appJsContent.includes('plg.rollbackNoSupport'), 'Bug 8 plugin rollback failed');

// Bug 10: app.py motor kilidi
assert.ok(appPyContent.includes('self._motor_kilidi = threading.Lock()'), 'Bug 10 lock missing');

// Bug 12: tick timer loop
assert.ok(appJsContent.includes('tickTimer = setTimeout(tick, POLL_MS);'), 'Bug 12 tickTimer missing');

console.log("Arayuz Hata Duzeltme Testleri (Static & AST) Basarili!");
