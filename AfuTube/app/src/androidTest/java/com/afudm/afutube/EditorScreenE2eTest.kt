package com.afudm.afutube

import android.content.Context
import android.graphics.Bitmap
import androidx.activity.ComponentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.assertExists
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.waitForIdle
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
                EditorScreen(initialProject = project, onAddClip = { _ -> }, onSave = {})
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

        composeRule.onNodeWithText("Oynat", substring = true, ignoreCase = true).assertExists()
        composeRule.onNodeWithText("Böl", substring = true, ignoreCase = true).assertExists()
        composeRule.onNodeWithText("Müzik", substring = true, ignoreCase = true).assertExists()
        composeRule.onNodeWithText("Kes", substring = true, ignoreCase = true).assertExists()
        composeRule.onNodeWithText("Yazı", substring = true, ignoreCase = true).assertExists()
    }
}
