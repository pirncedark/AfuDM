/* Browser download takeover with pause-first semantics. */
const AfuDownloadHandoff = (() => {
  const active = new Map();
  const recent = new Map();
  const acceptedIds = new Set();

  async function bounded(operation, milliseconds) {
    let timer;
    try {
      return await Promise.race([
        operation,
        new Promise((_, reject) => {
          timer = setTimeout(() => reject(new Error('Download handoff timed out')), milliseconds);
        }),
      ]);
    } finally {
      clearTimeout(timer);
    }
  }

  // Register before downloads.download: onCreated may precede its callback.
  const fallbackUrls = new Map();
  const fallbackIds = new Set();

  async function cleanup(id, deps) {
    await deps.cancel(id).catch(() => {});
    await deps.removeFile(id).catch(() => {});
    await deps.erase(id).catch(() => {});
  }

  async function restore(item, url, paused, canceled, deps) {
    if (paused) {
      const current = await deps.state(item.id);
      if (current.state === "complete") return;
      if (current.state === "in_progress" && current.paused) {
        try { await deps.resume(item.id); return; } catch (_) {}
      } else if (current.state === "in_progress") return;
      canceled = true;
    }
    if (!canceled) return;
    const marker = { consumed: false };
    fallbackUrls.set(url, marker);
    try {
      const id = await deps.download(item, url);
      if (!marker.consumed) fallbackIds.add(id);
      await deps.removeFile(item.id).catch(() => {});
      await deps.erase(item.id).catch(() => {});
    } finally {
      if (fallbackUrls.get(url) === marker) fallbackUrls.delete(url);
    }
  }

  async function handle(item, deps) {
    const url = item.finalUrl || item.url;
    if (!url || /^(blob|data):/i.test(url)) return false;
    if (fallbackIds.delete(item.id)) return false;
    const fallback = fallbackUrls.get(item.url) || fallbackUrls.get(url);
    if (fallback) {
      fallback.consumed = true;
      return false;
    }
    if (acceptedIds.has(item.id)) return true;
    const now = Date.now();
    for (const [seen, at] of recent) if (now - at > 5000) recent.delete(seen);

    // Stop every event immediately, including duplicates awaiting acceptance.
    const stopped = (async () => {
      try { await deps.pause(item.id); return { paused: true, canceled: false }; }
      catch (_) {
        try { await deps.cancel(item.id); return { paused: false, canceled: true }; }
        catch (error) {
          const current = await deps.state(item.id);
          if (current.state === "complete") return { paused: false, canceled: false };
          throw error;
        }
      }
    })();
    const previous = active.get(url);
    const operation = (async () => {
      const { paused, canceled } = await stopped;
      let handedOff = false;
      try {
        if (previous) handedOff = await previous;
        else if (recent.has(url)) handedOff = true;
        else {
          if (!(await bounded(deps.eligible(item, url), deps.timeoutMs || 15000))) return false;
          handedOff = !!(await bounded(deps.send(item, url), deps.timeoutMs || 15000));
        }
        if (!handedOff) return false;
        acceptedIds.add(item.id);
        await cleanup(item.id, deps);
        recent.set(url, Date.now());
        return true;
      } finally {
        if (!handedOff) await restore(item, url, paused, canceled, deps);
      }
    })();
    if (!previous) active.set(url, operation);
    try { return await operation; }
    finally { if (active.get(url) === operation) active.delete(url); }
  }

  return { handle };
})();
