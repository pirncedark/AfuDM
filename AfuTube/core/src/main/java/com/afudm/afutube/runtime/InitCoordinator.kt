package com.afudm.afutube.runtime

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Ensures that concurrent callers wait for the same initialization attempt. */
class InitCoordinator<T>(
    private val retryDelayMillis: Long = 30_000L,
    private val nowMillis: () -> Long = System::currentTimeMillis,
    private val initializer: suspend (T) -> Unit
) {
    private val mutex = Mutex()
    private var result: CompletableDeferred<Result<Unit>>? = null
    private var failedAtMillis: Long? = null

    suspend fun ensureInitialized(input: T) {
        val deferred = mutex.withLock {
            val existing = result
            if (existing != null && (failedAtMillis == null || nowMillis() - failedAtMillis!! < retryDelayMillis)) {
                existing
            } else CompletableDeferred<Result<Unit>>().also { created ->
                result = created
                failedAtMillis = null
                try {
                    initializer(input)
                    created.complete(Result.success(Unit))
                } catch (error: Throwable) {
                    failedAtMillis = nowMillis()
                    created.complete(Result.failure(error))
                }
            }
        }
        deferred.await().getOrThrow()
    }
}
