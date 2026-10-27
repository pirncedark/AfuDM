package com.afudm.afutube

import android.content.Context
import android.graphics.Bitmap
import androidx.activity.ComponentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.hasAnyAncestor
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.hasSetTextAction
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
        composeRule.onNodeWithTag("araclar").performScrollToIndex(0)
        composeRule.onNode(hasText("Kes") and hasAnyAncestor(hasTestTag("araclar"))).assertIsDisplayed()
        composeRule.onNode(hasText("Hız") and hasAnyAncestor(hasTestTag("araclar"))).assertIsDisplayed()
        val bitmap = composeRule.onRoot().captureToImage().asAndroidBitmap()
        evidence.outputStream().use { output ->
            assertTrue("Could not write editor screenshot", bitmap.compress(Bitmap.CompressFormat.PNG, 100, output))
        }
        assertTrue("Editor screenshot is missing", evidence.isFile && evidence.length() > 0)

        composeRule.onAllNodesWithText("Oynat", substring = true, ignoreCase = true).onFirst().assertExists()
        composeRule.onAllNodesWithText("Böl", substring = true, ignoreCase = true).onFirst().assertExists()
        composeRule.onAllNodesWithText("Müzik", substring = true, ignoreCase = true).onFirst().assertExists()
        listOf("Kes", "H\u0131z", "Ses", "M\u00fczik", "Yaz\u0131", "Filtre", "Oran", "Sesi ay\u0131r").forEach { tool ->
            composeRule.onNodeWithTag("araclar").performScrollToNode(hasText(tool))
            composeRule.onNode(hasText(tool) and hasAnyAncestor(hasTestTag("araclar"))).assertIsDisplayed()
        }
        composeRule.onNodeWithContentDescription("Klip 1").performClick()
        composeRule.onAllNodesWithText("Oynat").onFirst().performClick()
        composeRule.waitUntil(5_000) {
            composeRule.onAllNodesWithText("00:01 / 00:05", substring = true).fetchSemanticsNodes().isNotEmpty()
        }
        composeRule.onAllNodesWithText("Böl").onFirst().performClick()
        composeRule.onAllNodesWithText("2 klip").onFirst().assertExists()
        composeRule.onNodeWithTag("araclar").performScrollToNode(hasText("Müzik"))
        composeRule.onNode(hasText("Müzik") and hasAnyAncestor(hasTestTag("araclar"))).performClick()
        composeRule.onAllNodesWithText("AfuTube Müzik").onFirst().performClick()
        composeRule.onAllNodesWithText("Deneme müziği", substring = true).onFirst().performClick()
        composeRule.onAllNodesWithText("♪ Müzik izi", substring = true).onFirst().assertExists()
        composeRule.onAllNodesWithText("Kaldır").onFirst().performSemanticsAction(SemanticsActions.OnClick)
        composeRule.waitForIdle()
        composeRule.onNodeWithText("♪ Müzik izi", substring = true).assertDoesNotExist()

        // Yazı ekle, sonra oran 9:16; son ekran görüntüsü bu hâli gösterir.
        composeRule.onNodeWithTag("araclar").performScrollToNode(hasText("Yazı"))
        composeRule.onNode(hasText("Yazı") and hasAnyAncestor(hasTestTag("araclar"))).performClick()
        composeRule.onAllNodes(hasSetTextAction()).onFirst().performTextInput("Merhaba AfuTube")
        composeRule.onAllNodesWithText("Ekle").onFirst().performClick()
        composeRule.onAllNodesWithText("Merhaba AfuTube").onFirst().assertExists()
        composeRule.onNodeWithTag("araclar").performScrollToNode(hasText("Oran"))
        composeRule.onNode(hasText("Oran") and hasAnyAncestor(hasTestTag("araclar"))).performClick()
        composeRule.onAllNodesWithText("9:16").onFirst().performClick()
        composeRule.onAllNodesWithText("9:16").onFirst().assertExists()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("araclar").performScrollToIndex(0)
        composeRule.onNode(hasText("Kes") and hasAnyAncestor(hasTestTag("araclar"))).assertIsDisplayed()
        composeRule.onNode(hasText("H\u0131z") and hasAnyAncestor(hasTestTag("araclar"))).assertIsDisplayed()

        val finalBitmap = composeRule.onRoot().captureToImage().asAndroidBitmap()
        evidence.outputStream().use { output -> assertTrue("Could not write final editor screenshot", finalBitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) }
    }
}
