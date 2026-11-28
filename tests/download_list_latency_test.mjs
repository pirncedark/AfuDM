import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../rs/app/ui/app.js", import.meta.url), "utf8");
const slice = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)));
let now = 0, next, releaseSnapshot, drawerCalls = 0;
const never = new Promise(() => {});
const frames = [];
const elements = {};
const state = { items: [], controlOverrides: new Map(), lastDone: new Map(), trace: [], sessionBytes: 0 };
const sandbox = vm.createContext({
  state, performance: { now: () => now }, console,
  $: id => elements[id] ??= { style: {} },
  afudmHidden: () => false,
  call: method => {
    assert.equal(method, "snapshot");
    return new Promise(resolve => {
      releaseSnapshot = gids => resolve({ engine_ok: true, items: gids.map(gid => ({ gid })) });
    });
  },
  setTimeout: (callback, delay) => (next = { callback, delay }),
  clearTimeout: () => { next = undefined; },
  t: x => x, size: String, speed: String, drawTrace() {}, renderCounts() {},
  renderList: () => frames.push(state.items.map(item => item.gid)),
  renderDrawer: () => { drawerCalls++; return never; },
  bekleyenYokla: () => never,
});
vm.runInContext(slice("const POLL_MS", "const TRACE_POINTS") +
  slice("let offlineArdisik", 'if ($("engineRetry")) {'), sandbox);
const first = sandbox.tick();
now = 100;
releaseSnapshot(["already-active"]);
await first;
assert.deepEqual(frames[0], ["already-active"]);
assert.ok(next, "a slow detail panel or pending dialog must not block the list");
now += next.delay;
const second = next.callback();
await sandbox.tick(true); // Approval arrived after the snapshot began.
now += 100;
releaseSnapshot(["already-active", "external"]);
await second;
assert.ok(now <= 1000, "external additions must appear within one second in this scenario");
assert.deepEqual(frames[1], ["already-active", "external"]);
assert.equal(next.delay, 0, "fetch again immediately after an in-flight approval");
const third = next.callback();
releaseSnapshot(["already-active", "external", "approved"]);
await third;
assert.deepEqual(frames[2], ["already-active", "external", "approved"]);
assert.equal(drawerCalls, 1);
console.log("Headless list: startup 100ms, external addition at " + now + "ms, approval refresh delay 0ms (simulated clock)");
