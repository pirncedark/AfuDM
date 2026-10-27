package com.afudm.afutube

import android.media.MediaMetadataRetriever
import androidx.media3.common.util.UnstableApi
import androidx.media3.transformer.ExportException
import androidx.media3.transformer.ExportResult
import androidx.media3.transformer.Transformer
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import com.afudm.afutube.feature.editor.engine.CompositionBuilder
import com.afudm.afutube.feature.editor.model.EditorProject
import com.afudm.afutube.feature.editor.model.TextOverlay
import com.afudm.afutube.feature.editor.model.VideoClip
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
@UnstableApi
class EditorExportE2eTest {
    @Test fun trimsAddsTextAndExportsPlayableVideo() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val source = File(context.cacheDir, "editor-fixture.mp4")
        instrumentation.context.assets.open("editor-fixture.mp4").use { input -> source.outputStream().use(input::copyTo) }
        val project = EditorProject(
            clips = listOf(VideoClip("fixture", source.absolutePath, 5_000, trimStartMs = 1_000, trimEndMs = 4_000)),
            textOverlays = listOf(TextOverlay("title", "E2E", 0, 3_000))
        )
        val output = File(context.cacheDir, "editor-export-e2e.mp4")
        output.delete()
        val composition = CompositionBuilder.build(project).composition
        val finished = CountDownLatch(1)
        val failure = AtomicReference<ExportException?>()
        val transformer = Transformer.Builder(context).build()
        instrumentation.runOnMainSync {
            transformer.addListener(object : Transformer.Listener {
                override fun onCompleted(composition: androidx.media3.transformer.Composition, exportResult: ExportResult) { finished.countDown() }
                override fun onError(composition: androidx.media3.transformer.Composition, exportResult: ExportResult, exportException: ExportException) {
                    failure.set(exportException); finished.countDown()
                }
            })
            transformer.start(composition, output.absolutePath)
        }
        assertTrue("Transformer export timed out", finished.await(3, TimeUnit.MINUTES))
        assertNull(failure.get())
        assertTrue("Export file missing", output.isFile && output.length() > 0)
        val retriever = MediaMetadataRetriever()
        try {
            retriever.setDataSource(output.absolutePath)
            val duration = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)!!.toLong()
            assertTrue("Expected 3.0s ±0.3s, got ${duration}ms", duration in 2_700..3_300)
            assertEquals("Export must retain the fixture audio track", "yes", retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_HAS_AUDIO))
        } finally { retriever.release() }
        val evidence = File(context.getExternalFilesDir(null), "e2e-out/editor-export.png")
        evidence.parentFile?.mkdirs()
        assertTrue("Could not capture emulator screenshot", UiDevice.getInstance(instrumentation).takeScreenshot(evidence))
    }
}
