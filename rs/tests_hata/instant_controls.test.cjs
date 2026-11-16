const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../app/ui/app.js'), 'utf8');

function loadFunctions(source, stubs) {
  const ctx = vm.createContext({
    state: {
      items: [
        {gid: 'a', status: 'active'},
        {gid: 'b', status: 'paused'},
      ],
      lastDone: new Map([['a', 8], ['b', 13]]),
      selectedGids: new Set(['a', 'b']),
      selected: 'a',
    },
    renderCounts() {},
    renderList() {},
    renderDrawer() {},
    updateBulkRemoveBtn() {},
    toast() {},
    ...stubs,
  });
  vm.runInContext(source, ctx);
  return ctx;
}

const localRemoveFunctions = app.slice(
  app.indexOf('function uiKaldir('),
  app.indexOf('\n$("remGo").onclick', app.indexOf('function uiKaldir(')),
);
const bulkControls = app.slice(
  app.indexOf('async function topluKontrol('),
  app.indexOf('\n$("pauseAll").onclick', app.indexOf('async function topluKontrol(')),
);

test('bulk pause updates visible rows before the backend promise resolves', async () => {
  let resolveCall;
  const ctx = loadFunctions(bulkControls, {
    call: () => new Promise((resolve) => { resolveCall = resolve; }),
  });
  const pending = vm.runInContext('topluKontrol("pause_all")', ctx);
  assert.equal(ctx.state.items[0].status, 'paused');
  assert.equal(ctx.state.items[1].status, 'paused');
  resolveCall();
  await pending;
});

test('bulk pause restores visible rows when the backend rejects the command', async () => {
  const ctx = loadFunctions(bulkControls, {
    call: async () => { throw new Error('engine unavailable'); },
  });
  await vm.runInContext('topluKontrol("pause_all")', ctx);
  assert.equal(ctx.state.items[0].status, 'active');
  assert.equal(ctx.state.items[1].status, 'paused');
});

test('bulk resume updates paused rows before the backend promise resolves', async () => {
  let resolveCall;
  const ctx = loadFunctions(bulkControls, {
    call: () => new Promise((resolve) => { resolveCall = resolve; }),
  });
  const pending = vm.runInContext('topluKontrol("resume_all")', ctx);
  assert.equal(ctx.state.items[0].status, 'active');
  assert.equal(ctx.state.items[1].status, 'active');
  resolveCall();
  await pending;
});

test('optimistic remove hides rows and rollback restores them', () => {
  const ctx = loadFunctions(localRemoveFunctions);
  const removed = vm.runInContext('uiKaldir(["a"])', ctx);
  assert.deepEqual(Array.from(ctx.state.items, (item) => item.gid), ['b']);
  assert.deepEqual(Array.from(removed, (item) => item.gid), ['a']);
  ctx.removed = removed;
  vm.runInContext('uiGeriAl(removed)', ctx);
  assert.deepEqual(Array.from(ctx.state.items, (item) => item.gid), ['b', 'a']);
});

test('single and bulk remove handlers update local rows before awaiting the command', () => {
  const bulkStart = app.indexOf('const previous = uiKaldir(gids)');
  const bulkWait = app.indexOf('await Promise.allSettled', bulkStart);
  const singleStart = app.indexOf('const previous = uiKaldir([gid])');
  const singleWait = app.indexOf('await call("control", "remove", gid', singleStart);
  assert.ok(bulkStart >= 0 && bulkStart < bulkWait);
  assert.ok(singleStart >= 0 && singleStart < singleWait);
});
