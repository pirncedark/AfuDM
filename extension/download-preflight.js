/* Catch explicit file links before Chrome starts a native download. */
(() => {
  let enabled = false;
  let settings = {enabled:true, uzantiAcik:true};
  chrome.storage.local.get(settings).then(value => {
    settings = {...settings,...value};
    enabled = settings.enabled !== false && settings.uzantiAcik !== false;
  });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'local') return;
    for (const key of ['enabled','uzantiAcik']) if (changes[key]) settings[key] = changes[key].newValue;
    enabled = settings.enabled !== false && settings.uzantiAcik !== false;
  });
  const files = /\.(zip|rar|7z|tar|gz|bz2|xz|iso|exe|msi|apk|dmg|pdf|epub|docx?|xlsx?|pptx?|mp4|mkv|webm|mp3|flac|torrent)$/i;
  const fileEndpoint = /^\/(?:dosya|download|downloads)\/(?:f\/)?[^/]+\/?$/i;
  document.addEventListener('click', event => {
    if (!enabled || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.shiftKey || event.altKey || event.metaKey) return;
    const anchor = event.composedPath().map(node => node.closest?.('a[href]')).find(Boolean);
    if (!anchor) return;
    let url;
    try {url = new URL(anchor.href, location.href);} catch (_) {return;}
    if (!['http:','https:','magnet:'].includes(url.protocol)) return;
    if (url.protocol !== 'magnet:' && !anchor.hasAttribute('download') && !files.test(url.pathname) && !fileEndpoint.test(url.pathname)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const payload = {url:url.href, request_id:crypto.randomUUID(),
      filename:anchor.getAttribute('download') || undefined,
      kind:url.protocol === 'magnet:' || /\.torrent$/i.test(url.pathname) ? 'torrent' : 'http'};
    chrome.runtime.sendMessage({type:'downloadPreflight',payload}).catch(() => {
      // Never silently start a second download after an ambiguous acceptance.
      alert(chrome.i18n.getMessage('handoffRetry'));
    });
  }, true);
})();
