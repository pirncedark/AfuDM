package com.afudm.afutube.feature.downloads

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DownloadActionsTest {
    @Test fun folderPathBecomesDocumentsId() {
        val root = "/storage/emulated/0"
        assertEquals("primary:Download/AfuTube", folderDocumentId("/storage/emulated/0/Download/AfuTube/", root))
        assertEquals("primary:", folderDocumentId(root, root))
        assertEquals("primary:Download", folderDocumentId("/storage/emulated/0/Download", root))
    }

    @Test fun folderOutsideStorageRootHasNoDocumentId() {
        assertNull(folderDocumentId("/data/user/0/com.afudm.afutube/files", "/storage/emulated/0"))
        assertNull(folderDocumentId("/storage/emulated/1/Download", "/storage/emulated/0"))
        assertNull(folderDocumentId("/storage/emulated/0/Download", ""))
    }

    @Test fun appPrivateFolderIsMarkedHidden() {
        assertTrue(isHiddenAppFolder("primary:Android/data/com.afudm.afutube/files"))
        assertTrue(isHiddenAppFolder("primary:Android/obb/com.afudm.afutube"))
        assertFalse(isHiddenAppFolder("primary:Download/AfuTube"))
        assertFalse(isHiddenAppFolder(null))
    }
}
