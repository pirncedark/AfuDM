package com.afudm.afutube.runtime

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
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
}
