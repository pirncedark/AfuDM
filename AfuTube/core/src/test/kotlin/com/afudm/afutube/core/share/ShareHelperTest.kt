package com.afudm.afutube.core.share

import org.junit.Assert.assertEquals
import org.junit.Test

class ShareHelperTest {
    @Test fun whatsappIsPreferredWhenBothAreInstalled() {
        assertEquals("com.whatsapp", ShareHelper.preferredPackage { true })
    }

    @Test fun businessIsUsedWhenRegularWhatsappIsMissing() {
        assertEquals(
            "com.whatsapp.w4b",
            ShareHelper.preferredPackage { it == "com.whatsapp.w4b" }
        )
    }

    @Test fun chooserIsUsedWhenNeitherWhatsappIsInstalled() {
        assertEquals(null, ShareHelper.preferredPackage { false })
    }
}
