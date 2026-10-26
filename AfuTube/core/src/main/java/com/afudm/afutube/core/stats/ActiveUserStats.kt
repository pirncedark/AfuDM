package com.afudm.afutube.core.stats

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID

const val SAYAC_URL = "https://afu-sayac.REPLACE.workers.dev"

/** Cihazda kalici tutulan sayac durumu. */
interface SayacStore {
    var enabled: Boolean
    var installId: String?
    var lastPingDay: String?
}

interface SayacHttp {
    /** HTTP kodunu doner; ag hatasinda -1. */
    fun post(url: String, body: String): Int

    /** Govdeyi doner; hata/ag yoksa null. */
    fun get(url: String): String?
}

/**
 * Anonim gunluk sinyal: yalniz app, rastgele id ve surum gonderilir.
 * Kapaliyken hicbir istek gitmez.
 */
class ActiveUserStats(
    private val store: SayacStore,
    private val appVersion: String,
    private val http: SayacHttp = UrlConnectionSayacHttp,
    private val baseUrl: String = SAYAC_URL,
    private val today: () -> String = ::utcToday,
    private val newId: () -> String = { UUID.randomUUID().toString() },
) {
    data class Stats(val aktif7: Int, val aktif1: Int, val toplam: Int)

    var enabled: Boolean
        get() = store.enabled
        set(value) { store.enabled = value }

    /** Gunde en fazla bir kez ping atar. Basariliysa true doner. */
    suspend fun pingIfNeeded(): Boolean = withContext(Dispatchers.IO) {
        if (!store.enabled) return@withContext false
        val day = today()
        if (store.lastPingDay == day) return@withContext false
        val id = store.installId ?: newId().also { store.installId = it }
        val body = """{"app":"$APP","id":"$id","v":"${cleanVersion(appVersion)}"}"""
        val sent = http.post("$baseUrl/ping", body) == 204
        if (sent) store.lastPingDay = day
        sent
    }

    suspend fun fetchStats(): Stats? = withContext(Dispatchers.IO) {
        if (!store.enabled) return@withContext null
        val body = http.get("$baseUrl/stats?app=$APP") ?: return@withContext null
        parseStats(body)
    }

    companion object {
        const val APP = "afutube"
    }
}

fun activeUserStats(context: Context, appVersion: String): ActiveUserStats =
    ActiveUserStats(AndroidSayacStore(context), appVersion)

private class AndroidSayacStore(context: Context) : SayacStore {
    private val prefs = context.applicationContext.getSharedPreferences("afu_sayac", Context.MODE_PRIVATE)

    override var enabled: Boolean
        get() = prefs.getBoolean("enabled", true)
        set(value) { prefs.edit().putBoolean("enabled", value).apply() }

    override var installId: String?
        get() = prefs.getString("install_id", null)
        set(value) { prefs.edit().putString("install_id", value).apply() }

    override var lastPingDay: String?
        get() = prefs.getString("last_ping_day", null)
        set(value) { prefs.edit().putString("last_ping_day", value).apply() }
}

internal object UrlConnectionSayacHttp : SayacHttp {
    override fun post(url: String, body: String): Int = try {
        (URL(url).openConnection() as HttpURLConnection).run {
            connectTimeout = 8000
            readTimeout = 8000
            requestMethod = "POST"
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
            try {
                outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                responseCode
            } finally {
                disconnect()
            }
        }
    } catch (_: Exception) {
        -1
    }

    override fun get(url: String): String? = try {
        (URL(url).openConnection() as HttpURLConnection).run {
            connectTimeout = 8000
            readTimeout = 8000
            try {
                if (responseCode == 200) inputStream.bufferedReader().use { it.readText() } else null
            } finally {
                disconnect()
            }
        }
    } catch (_: Exception) {
        null
    }
}

internal fun parseStats(body: String): ActiveUserStats.Stats? {
    fun field(name: String): Int? =
        Regex("\"$name\"\\s*:\\s*(\\d+)").find(body)?.groupValues?.get(1)?.toIntOrNull()
    val aktif7 = field("aktif7") ?: return null
    val aktif1 = field("aktif1") ?: return null
    val toplam = field("toplam") ?: return null
    return ActiveUserStats.Stats(aktif7, aktif1, toplam)
}

internal fun utcToday(): String =
    SimpleDateFormat("yyyy-MM-dd", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }.format(Date())

/** JSON'a guvenle gomulebilmesi icin surum adini sadelestirir (en fazla 32 karakter). */
internal fun cleanVersion(version: String): String =
    version.filter { it.isLetterOrDigit() || it == '.' || it == '-' || it == '_' }.take(32)
