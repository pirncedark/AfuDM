package com.afudm.afutube.core.stats

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ActiveUserStatsTest {
    private class MemoryStore : SayacStore {
        override var enabled = true
        override var installId: String? = null
        override var lastPingDay: String? = null
    }

    private class FakeHttp(var postCode: Int = 204, var getBody: String? = null) : SayacHttp {
        val posts = mutableListOf<Pair<String, String>>()
        val gets = mutableListOf<String>()
        override fun post(url: String, body: String): Int {
            posts += url to body
            return postCode
        }
        override fun get(url: String): String? {
            gets += url
            return getBody
        }
    }

    private val id = "123e4567-e89b-42d3-a456-426614174000"

    @Test
    fun uuidIsCreatedOnceAndPersisted() = runBlocking {
        val store = MemoryStore()
        val http = FakeHttp()
        var day = "2026-10-26"
        var created = 0
        val stats = ActiveUserStats(store, "1.2.3", http, "https://test", { day }, { created++; id })

        stats.pingIfNeeded()
        day = "2026-10-27"
        stats.pingIfNeeded()

        assertEquals(1, created)
        assertEquals(id, store.installId)
        assertEquals(2, http.posts.size)
        assertTrue(http.posts.all { it.second.contains("\"id\":\"$id\"") })
    }

    @Test
    fun secondPingSameDayIsSkipped() = runBlocking {
        val store = MemoryStore()
        val http = FakeHttp()
        val stats = ActiveUserStats(store, "1.2.3", http, "https://test", { "2026-10-26" }, { id })

        assertTrue(stats.pingIfNeeded())
        assertFalse(stats.pingIfNeeded())

        assertEquals(1, http.posts.size)
        assertEquals("2026-10-26", store.lastPingDay)
    }

    @Test
    fun pingBodyContainsOnlyAppIdAndVersion() = runBlocking {
        val http = FakeHttp()
        val stats = ActiveUserStats(MemoryStore(), "1.2.3", http, "https://test", { "2026-10-26" }, { id })

        stats.pingIfNeeded()

        assertEquals("https://test/ping", http.posts.single().first)
        assertEquals("""{"app":"afutube","id":"$id","v":"1.2.3"}""", http.posts.single().second)
    }

    @Test
    fun disabledMakesNoRequests() = runBlocking {
        val store = MemoryStore().apply { enabled = false }
        val http = FakeHttp(getBody = """{"aktif7":5,"aktif1":2,"toplam":9}""")
        val stats = ActiveUserStats(store, "1.2.3", http, "https://test", { "2026-10-26" }, { id })

        assertFalse(stats.pingIfNeeded())
        assertNull(stats.fetchStats())

        assertTrue(http.posts.isEmpty())
        assertTrue(http.gets.isEmpty())
        assertNull(store.installId)
    }

    @Test
    fun failedPingIsRetriedSameDay() = runBlocking {
        val store = MemoryStore()
        val http = FakeHttp(postCode = 503)
        val stats = ActiveUserStats(store, "1.2.3", http, "https://test", { "2026-10-26" }, { id })

        assertFalse(stats.pingIfNeeded())
        http.postCode = 204
        assertTrue(stats.pingIfNeeded())

        assertEquals(2, http.posts.size)
        assertEquals("2026-10-26", store.lastPingDay)
    }

    @Test
    fun fetchStatsParsesResponse() = runBlocking {
        val http = FakeHttp(getBody = """{"aktif7":5,"aktif1":2,"toplam":40}""")
        val stats = ActiveUserStats(MemoryStore(), "1.2.3", http, "https://test", { "2026-10-26" }, { id })

        assertEquals(ActiveUserStats.Stats(5, 2, 40), stats.fetchStats())
        assertEquals("https://test/stats?app=afutube", http.gets.single())
    }

    @Test
    fun fetchStatsReturnsNullOnNetworkError() = runBlocking {
        val http = FakeHttp(getBody = null)
        val stats = ActiveUserStats(MemoryStore(), "1.2.3", http, "https://test", { "2026-10-26" }, { id })

        assertNull(stats.fetchStats())
    }
}
