package com.afudm.afutube.runtime

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

class InitCoordinatorTest {

    @Test
    fun `concurrent callers share one initialization`() = runBlocking {
        val calls = AtomicInteger(0)
        val coordinator = InitCoordinator<Unit> {
            calls.incrementAndGet()
        }

        val results = (1..8).map { async { coordinator.ensureInitialized(Unit) } }.awaitAll()

        assertEquals(List(8) { Unit }, results)
        assertEquals(1, calls.get())
    }

    @Test
    fun `failed initialization can be retried`() = runBlocking {
        val calls = AtomicInteger(0)
        var now = 0L
        val coordinator = InitCoordinator<Unit>(initializer = {
            if (calls.incrementAndGet() == 1) error("temporary")
        }, retryDelayMillis = 30_000, nowMillis = { now })

        assertThrows(RuntimeException::class.java) { runBlocking { coordinator.ensureInitialized(Unit) } }
        assertThrows(RuntimeException::class.java) { runBlocking { coordinator.ensureInitialized(Unit) } }
        assertEquals(1, calls.get())
        now += 30_000
        coordinator.ensureInitialized(Unit)

        assertEquals(2, calls.get())
    }
}
