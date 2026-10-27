package info.bigwizardmedia.wizardcut.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Icon
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.afudm.afutube.core.theme.AfuColors
import info.bigwizardmedia.wizardcut.R

/** Full-width main action of a screen: one per screen, 52.dp tall, AfuTube accent. */
@Composable
fun AfuPrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    testTag: String? = null,
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier
            .fillMaxWidth()
            .height(52.dp)
            .then(if (testTag != null) Modifier.testTag(testTag) else Modifier),
        shape = RoundedCornerShape(12.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = AfuColors.accent,
            contentColor = Color.White,
            disabledContainerColor = AfuColors.card,
            disabledContentColor = AfuColors.textMuted,
        ),
    ) {
        Text(text = text, style = MaterialTheme.typography.titleMedium)
    }
}

/** Card surface used for grouped content: AfuTube card color, 14.dp corners, 16.dp padding. */
@Composable
fun AfuCard(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = AfuColors.card,
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            content()
        }
    }
}

/**
 * Collapsed-by-default "Gelişmiş" card. Holds controls that most users never need.
 * The expanded state is remembered across recompositions and rotation.
 */
@Composable
fun AfuAdvancedSection(
    modifier: Modifier = Modifier,
    title: String = stringResource(R.string.afu_advanced_title),
    content: @Composable () -> Unit,
) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    AfuCard(modifier = modifier) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { expanded = !expanded },
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall,
                color = AfuColors.text,
                modifier = Modifier.weight(1f),
            )
            Icon(
                imageVector = if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                contentDescription = null,
                tint = AfuColors.textMuted,
                modifier = Modifier.size(20.dp),
            )
        }
        AnimatedVisibility(visible = expanded) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Spacer(modifier = Modifier.height(12.dp))
                content()
            }
        }
    }
}
