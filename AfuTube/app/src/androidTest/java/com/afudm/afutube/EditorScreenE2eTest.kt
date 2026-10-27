package com.afudm.afutube

import android.content.Context
import android.graphics.Bitmap
import androidx.activity.ComponentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.afudm.afutube.feature.editor.model.EditorProject
import com.afudm.afutube.feature.editor.model.VideoClip
import com.afudm.afutube.feature.editor.ui.EditorScreen
import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class EditorScreenE2eTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<ComponentActivity>()

    @Test
    fun opensEditorAndCapturesScreen() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val source = File(context.cacheDir, "editor-fixture.mp4")
        instrumentation.context.assets.open("editor-fixture.mp4").use { input ->
            source.outputStream().use(input::copyTo)
        }
        context.getSharedPreferences("editor_draft", Context.MODE_PRIVATE).edit()
            .remove("project")
            .putBoolean("intro_seen", true)
            .commit()

        val project = EditorProject(clips = listOf(VideoClip("fixture", source.absolutePath, 5_000)))
        composeRule.setContent {
            MaterialTheme {
                EditorScreen(initialProject = project, onAddClip = { _ -> }, onSave = {}, musicLibraryProvider = {
                    listOf(com.afudm.afutube.media.MusicTrack("content://test/fixture", "Deneme müziği", "AfuTube", durationMs = 5_000))
                })
            }
        }
        composeRule.waitForIdle()

        val evidence = File(context.getExternalFilesDir("e2e-out"), "editor-screen.png")
        evidence.parentFile?.mkdirs()
        val bitmap = composeRule.onRoot().captureToImage().asAndroidBitmap()
        evidence.outputStream().use { output ->
            assertTrue("Could not write editor screenshot", bitmap.compress(Bitmap.CompressFormat.PNG, 100, output))
        }
        assertTrue("Editor screenshot is missing", evidence.isFile && evidence.length() > 0)

        composeRule.onAllNodesWithText("Oynat", substring = true, ignoreCase = true).onFirst().assertExists()
        composeRule.onAllNodesWithText("Böl", substring = true, ignoreCase = true).onFirst().assertExists()
        composeRule.onAllNodesWithText("Müzik", substring = true, ignoreCase = true).onFirst().assertExists()
        composeRule.onAllNodesWithText("Kes", substring = true, ignoreCase = true).onFirst().assertExists()
        composeRule.onAllNodesWithText("Yazı", substring = true, ignoreCase = true).onFirst().assertExists()
        composeRule.onAllNodesWithText("Oran", substring = true).onFirst().performClick()
        composeRule.onAllNodesWithText("9:16", substring = true).onFirst().assertExists()
        composeRule.onNodeWithContentDescription("Klip 1").performClick()
        composeRule.onAllNodesWithText("Oynat").onFirst().performClick()
        composeRule.waitUntil(5_000) {
            composeRule.onAllNodesWithText("00:01 / 00:05", substring = true).fetchSemanticsNodes().isNotEmpty()
        }
        composeRule.onAllNodesWithText("Böl").onFirst().performClick()
        composeRule.onAllNodesWithText("2 klip").onFirst().assertExists()
        composeRule.onAllNodesWithText("Müzik", substring = true).onFirst().performClick()
        composeRule.onAllNodesWithText("AfuTube Müzik").onFirst().performClick()
        composeRule.onAllNodesWithText("Deneme müziği", substring = true).onFirst().performClick()
        composeRule.onAllNodesWithText("♪ Müzik izi", substring = true).onFirst().assertExists()
        composeRule.onAllNodesWithText("Kaldır").onFirst().performClick()
        composeRule.onNodeWithText("♪ Müzik izi", substring = true).assertDoesNotExist()

        val finalBitmap = composeRule.onRoot().captureToImage().asAndroidBitmap()
        evidence.outputStream().use { output -> assertTrue("Could not write final editor screenshot", finalBitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) }
    }
}
