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

  async function handle(item, deps) {
    const url = item.finalUrl || item.url;
    if (!url || /^(blob|data):/i.test(url)) return false;
    if (acceptedIds.has(item.id)) return true;
    const now = Date.now();
    for (const [seen, at] of recent) if (now - at > 5000) recent.delete(seen);
    if (active.has(url)) {
      const accepted = await active.get(url);
      if (accepted) {
        acceptedIds.add(item.id);
        await deps.cancel(item.id).catch(() => {});
        await deps.removeFile(item.id).catch(() => {});
        await deps.erase(item.id).catch(() => {});
      }
      return accepted;
    }
    if (recent.has(url)) {
      acceptedIds.add(item.id);
      await deps.cancel(item.id).catch(() => {});
      await deps.removeFile(item.id).catch(() => {});
      await deps.erase(item.id).catch(() => {});
      return true;
    }

    const operation = (async () => {
      let paused = false;
      let handedOff = false;
      try {
        await deps.pause(item.id);
        paused = true;
      } catch (_) {
        // The browser may already have completed or the user may have stopped it.
      }
      try {
        if (!(await bounded(deps.eligible(item, url), deps.timeoutMs || 15000))) return false;
        const current = await deps.state(item.id);
        if (current.state === "complete" || current.state === "interrupted") return false;
        const accepted = await bounded(deps.send(item, url), deps.timeoutMs || 15000);
        if (!accepted) return false;
        handedOff = true;
        acceptedIds.add(item.id);
        await deps.cancel(item.id).catch(() => {});
        await deps.removeFile(item.id).catch(() => {});
        await deps.erase(item.id).catch(() => {});
        recent.set(url, Date.now());
        return true;
      } finally {
        if (paused && !handedOff) {
          const current = await deps.state(item.id).catch(() => ({}));
          if (current.state === "in_progress" && current.paused) await deps.resume(item.id).catch(() => {});
        }
      }
    })();
    active.set(url, operation);
    try { return await operation; }
    finally { if (active.get(url) === operation) active.delete(url); }
  }

  return { handle };
})();
