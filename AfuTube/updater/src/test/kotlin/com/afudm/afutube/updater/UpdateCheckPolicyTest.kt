package com.afudm.afutube.updater

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateCheckPolicyTest {
    private val day = 24L * 60 * 60 * 1000

    @Test
    fun checksOnFirstLaunchAndAfterOneDayButNotAt23Hours() {
        assertTrue(UpdateCheckPolicy.shouldCheckAutomatically(null, 0, day, enabled = true))
        assertFalse(UpdateCheckPolicy.shouldCheckAutomatically(0, 23 * 60 * 60 * 1000L, day, enabled = true))
        assertTrue(UpdateCheckPolicy.shouldCheckAutomatically(0, 25 * 60 * 60 * 1000L, day, enabled = true))
    }

    @Test
    fun manualCheckAlwaysRunsAndDisabledAutomaticCheckDoesNot() {
        assertTrue(UpdateCheckPolicy.shouldCheckAutomatically(0, 1, day, enabled = true, manual = true))
        assertFalse(UpdateCheckPolicy.shouldCheckAutomatically(null, day, day, enabled = false))
    }
}
