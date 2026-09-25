package com.afudm.afutube

import android.annotation.SuppressLint
import android.net.Uri
import android.webkit.CookieManager
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.webkit.WebMessageCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import androidx.webkit.WebSettingsCompat
import com.afudm.afutube.core.theme.AfuColors
import com.afudm.afutube.downloader.DownloadEngine
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

private const val CAPTURE_SCRIPT = """
(() => {
 const send=(url,type='',size=0)=>{try{if(typeof url==='string'&&url.length<=4096&&/^https?:\/\//i.test(url)) window.AfuCapture?.postMessage(JSON.stringify({url,type:String(type||'').slice(0,160),size:Number(size)||0}));}catch(_){}};
 const f=window.fetch;if(f)window.fetch=function(){const p=f.apply(this,arguments);try{p.then(r=>{const t=r.headers.get('content-type')||'';if(/mpegurl|dash\+xml|^video\/(mp4|webm|x-m4v|quicktime)/i.test(t))send(r.url,t,parseInt(r.headers.get('content-length')||'0',10))}).catch(()=>{})}catch(_){}return p};
 const xo=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(m,u){this.__afuUrl=String(u||'');return xo.apply(this,arguments)};
 const xs=XMLHttpRequest.prototype.send;XMLHttpRequest.prototype.send=function(){this.addEventListener('load',()=>{try{const t=this.getResponseHeader('content-type')||'';if(/mpegurl|dash\+xml|^video\/(mp4|webm|x-m4v|quicktime)/i.test(t))send(this.responseURL||this.__afuUrl,t,parseInt(this.getResponseHeader('content-length')||'0',10))}catch(_){}});return xs.apply(this,arguments)};
 const scan=()=>document.querySelectorAll('video,source').forEach(e=>{const u=e.currentSrc||e.src;if(u&&!u.startsWith('blob:'))send(u,e.type||'')});new MutationObserver(scan).observe(document,{subtree:true,childList:true,attributes:true});scan();
 const req=navigator.requestMediaKeySystemAccess;if(req)navigator.requestMediaKeySystemAccess=function(){try{window.AfuCapture?.postMessage(JSON.stringify({drm:true}))}catch(_){}return req.apply(this,arguments)};
})();
"""

@SuppressLint("SetJavaScriptEnabled")
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BrowserScreen(startUrl: String, onClose: () -> Unit, onDownload: (DownloadEngine.DownloadRequest) -> Unit, onAnalyzePage: (String) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val captured = remember { mutableStateListOf<MediaSniffer.Candidate>() }
    val variantUrls = remember { mutableStateListOf<String>() }
    var webView by remember { mutableStateOf<WebView?>(null) }
    var title by remember { mutableStateOf("Tarayıcı") }
    var pageUrl by remember { mutableStateOf(startUrl) }
    var showSheet by remember { mutableStateOf(false) }
    var protectedContent by remember { mutableStateOf(false) }
    val supportedPageUrl = remember(pageUrl) { pageUrl.takeIf(SupportedPageDetector::supports) }
    val safeStart = remember(startUrl) { startUrl.takeIf(MediaSniffer::isHttpUrl) ?: "about:blank" }

    fun report(url: String, contentType: String = "", size: Long = 0, rangeRequest: Boolean = false) {
        if (protectedContent || url in variantUrls || MediaSniffer.shouldIgnoreRequest(url, pageUrl)) return
        val kind = MediaSniffer.classify(url, contentType) ?: return
        val existing = captured.indexOfFirst { it.url == url }
        if (MediaSniffer.isSegment(url, rangeRequest)) return
        if (kind == MediaSniffer.Kind.MP4 && size in 1 until 300L * 1024) {
            if (existing >= 0) captured.removeAt(existing)
            return
        }
        if (existing >= 0) captured[existing] = captured[existing].copy(contentType = contentType.ifBlank { captured[existing].contentType }, size = size.coerceAtLeast(captured[existing].size))
        else {
            captured.add(MediaSniffer.Candidate(url, kind, contentType, size))
            while (captured.size > 40) captured.removeAt(captured.lastIndex)
        }
        val ranked = MediaSniffer.rankCandidates(captured.toList(), pageUrl)
        captured.clear(); captured.addAll(ranked)
        if (kind == MediaSniffer.Kind.HLS && captured.none { it.url == url && it.quality.isNotEmpty() }) {
            val masterReferer = pageUrl
            val masterUserAgent = webView?.settings?.userAgentString.orEmpty()
            val masterCookie = CookieManager.getInstance().getCookie(url).orEmpty()
            scope.launch(Dispatchers.IO) {
                val master = readMaster(url, masterReferer, masterUserAgent, masterCookie)
                if (master != null) withContext(Dispatchers.Main) {
                    variantUrls.addAll(MediaSniffer.masterVariants(master, url).take(100))
                    captured.removeAll { it.url in variantUrls }
                    val i = captured.indexOfFirst { it.url == url }
                    val qualities = MediaSniffer.masterQualities(master)
                    if (i >= 0 && qualities.isNotEmpty()) captured[i] = captured[i].copy(quality = qualities.joinToString(" · "))
                }
            }
        }
    }

    Box(Modifier.fillMaxSize().background(AfuColors.bg)) {
        Column(Modifier.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().background(AfuColors.card).padding(horizontal = 4.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { if (webView?.canGoBack() == true) webView?.goBack() else onClose() }) { Icon(Icons.Default.ArrowBack, "Geri", tint = AfuColors.text) }
                Column(Modifier.weight(1f)) {
                    Text(title.ifBlank { "Tarayıcı" }, maxLines = 1, overflow = TextOverflow.Ellipsis, color = AfuColors.text, style = MaterialTheme.typography.titleSmall)
                    Text(runCatching { Uri.parse(pageUrl).host.orEmpty() }.getOrDefault(""), maxLines = 1, overflow = TextOverflow.Ellipsis, color = AfuColors.textMuted, style = MaterialTheme.typography.labelSmall)
                }
                IconButton(onClick = { webView?.reload() }) { Icon(Icons.Default.Refresh, "Yenile", tint = AfuColors.text) }
                IconButton(onClick = onClose) { Icon(Icons.Default.Close, "Kapat", tint = AfuColors.text) }
            }
            AndroidView(factory = { ctx ->
                WebView(ctx).apply {
                    webView = this
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    settings.mediaPlaybackRequiresUserGesture = true
                    settings.allowFileAccess = false
                    settings.allowContentAccess = false
                    settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
                    CookieManager.getInstance().setAcceptThirdPartyCookies(this, true)
                    CookieManager.getInstance().setAcceptCookie(true)
                    if (WebViewFeature.isFeatureSupported(WebViewFeature.SAFE_BROWSING_ENABLE)) WebSettingsCompat.setSafeBrowsingEnabled(settings, true)
                    if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
                        WebViewCompat.addWebMessageListener(this, "AfuCapture", setOf("*")) { _, message: WebMessageCompat, _, _, _ ->
                            val raw = message.data?.take(8192) ?: return@addWebMessageListener
                            if (raw.contains("\"drm\":true")) { scope.launch(Dispatchers.Main) { protectedContent = true; captured.clear() }; return@addWebMessageListener }
                            val match = Regex("""\"url\"\s*:\s*\"([^\"]{1,4096})\"""").find(raw) ?: return@addWebMessageListener
                            val url = match.groupValues[1].replace("\\/", "/").replace("\\u0026", "&")
                            val type = Regex("""\"type\"\s*:\s*\"([^\"]{0,160})\"""").find(raw)?.groupValues?.get(1).orEmpty()
                            val size = Regex("""\"size\"\s*:\s*(\d+)""").find(raw)?.groupValues?.get(1)?.toLongOrNull() ?: 0L
                            if (MediaSniffer.isHttpUrl(url)) scope.launch(Dispatchers.Main) { report(url, type.take(160), size) }
                        }
                        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) WebViewCompat.addDocumentStartJavaScript(this, CAPTURE_SCRIPT, setOf("*"))
                    } else {
                        addJavascriptInterface(object { @android.webkit.JavascriptInterface fun postMessage(data: String) {
                            val raw = data.take(8192)
                            if (raw.contains("\"drm\":true")) { scope.launch(Dispatchers.Main) { protectedContent = true; captured.clear() }; return }
                            val url = Regex("""\"url\"\s*:\s*\"([^\"]{1,4096})\"""").find(raw)?.groupValues?.get(1)?.replace("\\/", "/") ?: return
                            val type = Regex("""\"type\"\s*:\s*\"([^\"]{0,160})\"""").find(raw)?.groupValues?.get(1).orEmpty()
                            val size = Regex("""\"size\"\s*:\s*(\d+)""").find(raw)?.groupValues?.get(1)?.toLongOrNull() ?: 0L
                            if (MediaSniffer.isHttpUrl(url)) scope.launch(Dispatchers.Main) { report(url, type, size) }
                        } }, "AfuCapture")
                    }
                    webViewClient = object : WebViewClient() {
                        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                            !MediaSniffer.isHttpUrl(request.url.toString())
                        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                            val url = request.url.toString()
                            if (url.length <= 4096) view.post { report(url, rangeRequest = request.requestHeaders.keys.any { it.equals("Range", true) }) }
                            return null
                        }
                        override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
                            super.onPageStarted(view, url, favicon)
                            url?.takeIf(MediaSniffer::isHttpUrl)?.let { pageUrl = it; captured.clear() }
                            if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER) || !WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) view.evaluateJavascript(CAPTURE_SCRIPT, null)
                        }
                        override fun onPageFinished(view: WebView, url: String?) { super.onPageFinished(view, url); title = view.title.orEmpty().ifBlank { "Tarayıcı" }; url?.let { pageUrl = it } }
                    }
                    loadUrl(safeStart)
                }
            }, modifier = Modifier.fillMaxSize())
        }
        if (captured.isNotEmpty() || supportedPageUrl != null) {
            Row(Modifier.align(Alignment.BottomEnd).padding(16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (supportedPageUrl != null) Surface(onClick = { onAnalyzePage(supportedPageUrl) }, shape = RoundedCornerShape(24.dp), color = AfuColors.card, border = BorderStroke(1.dp, AfuColors.accent), shadowElevation = 4.dp) {
                    Row(Modifier.padding(horizontal = 14.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Download, null, tint = AfuColors.accent, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp)); Text("Video", color = AfuColors.text)
                    }
                }
                if (captured.isNotEmpty()) {
                    Surface(onClick = { showSheet = true }, modifier = Modifier.semantics { contentDescription = "Yakalanan videolar" }, shape = RoundedCornerShape(24.dp), color = AfuColors.card, border = BorderStroke(1.dp, AfuColors.accent), shadowElevation = 4.dp) {
                        Row(Modifier.padding(horizontal = 16.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Download, null, tint = AfuColors.accent, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("${captured.size} video", color = AfuColors.text)
                        }
                    }
                }
            }
        }
        if (protectedContent) Surface(Modifier.align(Alignment.BottomCenter).padding(16.dp), color = AfuColors.card, shape = RoundedCornerShape(12.dp)) {
            Text("Korumalı içerik", Modifier.padding(horizontal = 16.dp, vertical = 10.dp), color = AfuColors.textMuted)
        }
    }

    if (showSheet) ModalBottomSheet(onDismissRequest = { showSheet = false }, containerColor = AfuColors.card) {
        Text("Yakalanan videolar", modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp), color = AfuColors.text, style = MaterialTheme.typography.titleMedium)
        supportedPageUrl?.let { url ->
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Bu sayfadaki video (önerilen)", color = AfuColors.text)
                    Text(url, color = AfuColors.textMuted, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.labelSmall)
                }
                TextButton(onClick = { onAnalyzePage(url) }) { Text("⬇ Video", color = AfuColors.text) }
            }
        }
        LazyColumn(contentPadding = PaddingValues(bottom = 24.dp)) {
            items(captured, key = { it.url }) { media ->
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        if (captured.firstOrNull()?.url == media.url) Text("Önerilen", color = AfuColors.textMuted, style = MaterialTheme.typography.labelSmall)
                        Text(media.kind.label + media.quality.takeIf(String::isNotBlank)?.let { " · $it" }.orEmpty(), color = AfuColors.text)
                        Text(media.url.substringAfterLast('/').take(52), color = AfuColors.textMuted, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.labelSmall)
                        if (media.size > 0) Text("${media.size / 1024} KB", color = AfuColors.textMuted, style = MaterialTheme.typography.labelSmall)
                    }
                    TextButton(onClick = {
                        val headers = linkedMapOf("Referer" to pageUrl.take(2048), "User-Agent" to (webView?.settings?.userAgentString.orEmpty().take(512)))
                        CookieManager.getInstance().getCookie(media.url)?.takeIf(String::isNotBlank)?.take(4096)?.let { headers["Cookie"] = it }
                        val cleanTitle = title.replace(Regex("[\\\\/:*?\"<>|]"), "_").take(100).ifBlank { "Video" }
                        onDownload(DownloadEngine.DownloadRequest(url = media.url, formatId = if (media.kind == MediaSniffer.Kind.HLS) "bestvideo[height<=720]+bestaudio/best[height<=720]/best" else "bestvideo+bestaudio/best", title = cleanTitle, mergeAV = media.kind != MediaSniffer.Kind.MP4, headers = headers))
                        android.widget.Toast.makeText(context, "İndirme başladı", android.widget.Toast.LENGTH_SHORT).show()
                    }) { Text("İndir", color = AfuColors.text) }
                }
            }
        }
    }
    DisposableEffect(Unit) { onDispose { webView?.destroy(); webView = null } }
}

private fun readMaster(url: String, referer: String, userAgent: String, cookie: String): String? = runCatching {
    val connection = URL(url).openConnection() as HttpURLConnection
    connection.connectTimeout = 4000; connection.readTimeout = 4000; connection.setRequestProperty("Referer", referer)
    if (userAgent.isNotBlank()) connection.setRequestProperty("User-Agent", userAgent)
    if (cookie.isNotBlank()) connection.setRequestProperty("Cookie", cookie)
    connection.inputStream.use { input ->
        val buffer = ByteArray(8192)
        val output = java.io.ByteArrayOutputStream()
        while (output.size() < 256 * 1024) {
            val count = input.read(buffer, 0, minOf(buffer.size, 256 * 1024 - output.size()))
            if (count < 0) break
            output.write(buffer, 0, count)
        }
        output.toString("UTF-8")
    }
}.getOrNull()
