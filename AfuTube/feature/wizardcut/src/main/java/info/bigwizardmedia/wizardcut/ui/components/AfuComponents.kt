package info.bigwizardmedia.wizardcut.ui.components

import android.provider.Settings
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import info.bigwizardmedia.wizardcut.R

/** Edit-screen palette: AfuTube's dark tokens only (no light theme in 1.14.1). */
data class AfuEditPalette(
    val card: Color,
    val accent: Color,
    val onAccent: Color,
    val text: Color,
    val textMuted: Color,
    val disabled: Color,
)

fun afuEditPalette(): AfuEditPalette = AfuEditPalette(
    card = com.afudm.afutube.core.theme.AfuColors.card,
    accent = com.afudm.afutube.core.theme.AfuColors.accent,
    onAccent = Color.White,
    text = com.afudm.afutube.core.theme.AfuColors.text,
    textMuted = com.afudm.afutube.core.theme.AfuColors.textMuted,
    disabled = com.afudm.afutube.core.theme.AfuColors.card,
)

/** True when the system animator scale is 0 (Reduce Motion / remove animations). */
@Composable
fun rememberReduceMotion(): Boolean {
    val context = LocalContext.current
    return remember(context) {
        runCatching {
            Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
        }.getOrDefault(false)
    }
}

/** Full-width main action of a screen: one per screen, 52.dp tall (>= 48.dp touch target). */
@Composable
fun AfuPrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    testTag: String? = null,
) {
    val palette = afuEditPalette()
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 52.dp)
            .then(if (testTag != null) Modifier.testTag(testTag) else Modifier),
        shape = RoundedCornerShape(12.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = palette.accent,
            contentColor = palette.onAccent,
            disabledContainerColor = palette.disabled,
            disabledContentColor = palette.textMuted,
        ),
    ) {
        Text(text = text, style = MaterialTheme.typography.titleMedium)
    }
}

/** Grouped content surface: card color, 14.dp corners, 16.dp padding. */
@Composable
fun AfuCard(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    val palette = afuEditPalette()
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = palette.card,
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            content()
        }
    }
}

/**
 * Collapsed-by-default "Gelişmiş" card. Holds controls most users never need.
 * Expanded state survives rotation; motion is dropped when Reduce Motion is on.
 */
@Composable
fun AfuAdvancedSection(
    modifier: Modifier = Modifier,
    title: String = stringResource(R.string.afu_advanced_title),
    content: @Composable () -> Unit,
) {
    val palette = afuEditPalette()
    val reduceMotion = rememberReduceMotion()
    var expanded by rememberSaveable { mutableStateOf(false) }
    AfuCard(modifier = modifier) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 48.dp)
                .clickable { expanded = !expanded },
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall,
                color = palette.text,
                modifier = Modifier.weight(1f),
            )
            Icon(
                imageVector = if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                contentDescription = null,
                tint = palette.textMuted,
                modifier = Modifier.size(20.dp),
            )
        }
        AnimatedVisibility(
            visible = expanded,
            enter = if (reduceMotion) EnterTransition.None else fadeIn() + expandVertically(),
            exit = if (reduceMotion) ExitTransition.None else fadeOut() + shrinkVertically(),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Spacer(modifier = Modifier.height(12.dp))
                content()
            }
        }
    }
}
