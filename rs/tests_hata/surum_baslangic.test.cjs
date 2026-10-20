const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const bridge = fs.readFileSync(path.join(__dirname, '../app/ui/tauri_kopru.js'), 'utf8');
const app = fs.readFileSync(path.join(__dirname, '../app/ui/app.js'), 'utf8');
const readyHandler = app.slice(app.indexOf('window.addEventListener("pywebviewready"'), app.indexOf('\nafudmSetInterval(', app.indexOf('window.addEventListener("pywebviewready"')));
const versionLoader = app.slice(app.indexOf('async function surumuYukle()'), app.indexOf('\nasync function surumuCiz()'));

function fixture(readyState = 'loading', failures = 0) {
  const window = new EventTarget(), document = new EventTarget();
  document.readyState = readyState;
  const timers = [], calls = [], elements = {brandSurum: {}, globalModel: {}};
  window.__TAURI__ = {core: {invoke: async () => {}}};
  const ctx = vm.createContext({
    window, document, Event, Element: class {},
    state: {ready: false}, surumBilgisi: null,
    $: id => elements[id],
    setTimeout: (fn, delay) => {timers.push({fn, delay});},
    afudmHidden: () => false,
    guncellemeOtomatikKontrol: () => calls.push('update'),
    call: async method => {
      calls.push(method);
      if (failures-- > 0) throw new Error('temporary startup failure');
      return {surum: '3.1.2'};
    },
  });
  window.afudmPencere = () => calls.push('window');
  vm.runInContext(versionLoader, ctx);
  const flush = async () => {for (let i = 0; i < 20; i++) await Promise.resolve();};
  const drain = async () => {
    await flush();
    while (timers.length) {timers.shift().fn(); await flush();}
  };
  return {ctx, window, document, timers, calls, elements, flush, drain};
}

test('delayed app script still receives readiness, version and startup update', async () => {
  const f = fixture();
  vm.runInContext(bridge, f.ctx);
  // Browser may run timers while fetching the following app script.
  await f.drain();
  vm.runInContext(readyHandler, f.ctx);
  f.document.readyState = 'interactive';
  f.document.dispatchEvent(new Event('DOMContentLoaded'));
  await f.drain();
  assert.equal(f.ctx.state.ready, true);
  assert.equal(f.elements.brandSurum.textContent, 'v3.1.2');
  assert.equal(f.elements.globalModel.textContent, 'AfuDM v3.1.2');
  assert.equal(f.calls.filter(c => c === 'update').length, 1);
  f.document.dispatchEvent(new Event('DOMContentLoaded'));
  await f.drain();
  assert.equal(f.calls.filter(c => c === 'update').length, 1);
});

test('bridge loaded after DOM readiness still notifies the app', async () => {
  const f = fixture('complete');
  vm.runInContext(readyHandler, f.ctx);
  vm.runInContext(bridge, f.ctx);
  await f.drain();
  assert.equal(f.ctx.state.ready, true);
  assert.equal(f.elements.brandSurum.textContent, 'v3.1.2');
});

test('version loader retries two transient failures and caches success', async () => {
  const f = fixture('complete', 2);
  const result = vm.runInContext('surumuYukle()', f.ctx);
  await f.drain();
  assert.equal((await result)?.surum, '3.1.2');
  assert.equal(f.calls.length, 3);
  assert.equal(f.elements.brandSurum.textContent, 'v3.1.2');
  assert.equal(f.elements.globalModel.textContent, 'AfuDM v3.1.2');
  await vm.runInContext('surumuYukle()', f.ctx);
  assert.equal(f.calls.length, 3);
});

test('persistent version failure stops after three attempts', async () => {
  const f = fixture('complete', 99);
  const result = vm.runInContext('surumuYukle()', f.ctx);
  await f.drain();
  assert.equal(await result, null);
  assert.equal(f.calls.length, 3);
  assert.equal(f.timers.length, 0);
});
