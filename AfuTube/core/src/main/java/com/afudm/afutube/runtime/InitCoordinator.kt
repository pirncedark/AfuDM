package com.afudm.afutube.runtime

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Ensures that concurrent callers wait for the same initialization attempt. */
class InitCoordinator<T>(private val initializer: suspend (T) -> Unit) {
    private val mutex = Mutex()
    private var result: CompletableDeferred<Result<Unit>>? = null

    suspend fun ensureInitialized(input: T) {
        val deferred = mutex.withLock {
            result ?: CompletableDeferred<Result<Unit>>().also { created ->
                result = created
                try {
                    initializer(input)
                    created.complete(Result.success(Unit))
                } catch (error: Throwable) {
                    created.complete(Result.failure(error))
                }
            }
        }
        deferred.await().getOrThrow()
    }
}
