package info.bigwizardmedia.wizardcut.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import com.afudm.afutube.core.theme.AfuColors
import info.bigwizardmedia.wizardcut.engine.AppearanceMode

// AfuTube: WizardCut paleti AfuTube renk tokenlarına (core/theme/AfuColors) bağlandı.
// Adlar (Mocha.*) WizardCut kodunda her yerde kullanıldığı için korunur; değerler AfuTube'un.
object Mocha {
    val Midnight = AfuColors.bg
    val Crust = AfuColors.bg
    val Mantle = AfuColors.bg
    val Base = AfuColors.bg
    val Panel = AfuColors.surface
    val PanelRaised = AfuColors.card
    val PanelHighest = AfuColors.card
    val CardStroke = AfuColors.textMuted.copy(alpha = 0.28f)
    val CardStrokeStrong = AfuColors.textMuted.copy(alpha = 0.55f)
    val Glow = AfuColors.accent.copy(alpha = 0.40f)
    val GlowSoft = AfuColors.accent.copy(alpha = 0.20f)
    val GlowWarm = AfuColors.accentAlt.copy(alpha = 0.20f)
    val Surface0 = AfuColors.card
    val Surface1 = AfuColors.card
    val Surface2 = AfuColors.textMuted.copy(alpha = 0.35f)
    val Overlay0 = AfuColors.textMuted
    val Overlay1 = AfuColors.textMuted
    val Overlay2 = AfuColors.textMuted
    val Subtext0 = AfuColors.textMuted
    val Subtext1 = AfuColors.text.copy(alpha = 0.75f)
    val Text = AfuColors.text
    val Lavender = AfuColors.accent
    val Blue = AfuColors.accent
    val Sapphire = AfuColors.accent
    val Sky = AfuColors.accent
    val Teal = AfuColors.accent
    val Green = AfuColors.success
    val Yellow = AfuColors.warning
    val Peach = AfuColors.warning
    val Maroon = AfuColors.error
    val Red = AfuColors.error
    val Mauve = AfuColors.accentAlt
    val Pink = AfuColors.accentAlt
    val Flamingo = AfuColors.accentAlt
    val Rosewater = AfuColors.accentAlt
    val Wizard = AfuColors.accent
    val WizardDeep = AfuColors.accentAlt
}

/**
 * Stable media/category accents. Feature surfaces may use these to preserve
 * identity, but structural chrome and readable content must use
 * [LocalClearCutColors] so High Contrast Dark can strengthen them.
 */
object ClearCutAccents {
    /** Stable neutral accent for content that is defined outside composition. */
    val Neutral = Mocha.Subtext0
    val Lavender = Mocha.Lavender
    val Blue = Mocha.Blue
    val Sapphire = Mocha.Sapphire
    val Sky = Mocha.Sky
    val Teal = Mocha.Teal
    val Green = Mocha.Green
    val Yellow = Mocha.Yellow
    val Peach = Mocha.Peach
    val Maroon = Mocha.Maroon
    val Red = Mocha.Red
    val Mauve = Mocha.Mauve
    val Pink = Mocha.Pink
    val Flamingo = Mocha.Flamingo
    val Rosewater = Mocha.Rosewater
}

private val ClearCutDarkColorScheme = darkColorScheme(
    primary = Mocha.Wizard,
    onPrimary = AfuColors.text,
    primaryContainer = Mocha.Wizard.copy(alpha = 0.18f),
    onPrimaryContainer = Mocha.Wizard,
    secondary = Mocha.Teal,
    onSecondary = AfuColors.text,
    secondaryContainer = Mocha.Teal.copy(alpha = 0.16f),
    onSecondaryContainer = Mocha.Teal,
    tertiary = Mocha.Mauve,
    onTertiary = AfuColors.text,
    tertiaryContainer = Mocha.Mauve.copy(alpha = 0.16f),
    onTertiaryContainer = Mocha.Mauve,
    error = Mocha.Red,
    onError = Mocha.Crust,
    errorContainer = Mocha.Red.copy(alpha = 0.3f),
    onErrorContainer = Mocha.Red,
    background = Mocha.Midnight,
    onBackground = Mocha.Text,
    surface = Mocha.Panel,
    onSurface = Mocha.Text,
    surfaceVariant = Mocha.PanelRaised,
    onSurfaceVariant = Mocha.Subtext1,
    outline = Mocha.CardStrokeStrong,
    outlineVariant = Mocha.CardStroke,
    inverseSurface = Mocha.Text,
    inverseOnSurface = Mocha.Base,
    inversePrimary = Mocha.WizardDeep,
    surfaceDim = Mocha.Crust,
    surfaceBright = Mocha.PanelHighest,
    surfaceContainerLowest = Mocha.Midnight,
    surfaceContainerLow = Mocha.Panel,
    surfaceContainer = Mocha.Mantle,
    surfaceContainerHigh = Mocha.PanelRaised,
    surfaceContainerHighest = Mocha.PanelHighest
)

private val ClearCutHighContrastColorScheme = darkColorScheme(
    primary = Mocha.Wizard,
    onPrimary = Mocha.Crust,
    primaryContainer = Mocha.Wizard,
    onPrimaryContainer = Mocha.Crust,
    secondary = Mocha.Teal,
    onSecondary = Mocha.Crust,
    secondaryContainer = Mocha.Teal,
    onSecondaryContainer = Mocha.Crust,
    tertiary = Mocha.Mauve,
    onTertiary = Mocha.Crust,
    tertiaryContainer = Mocha.Mauve,
    onTertiaryContainer = Mocha.Crust,
    error = Mocha.Red,
    onError = Mocha.Crust,
    errorContainer = Mocha.Red,
    onErrorContainer = Mocha.Crust,
    background = Color(0xFF05070D),
    onBackground = Color(0xFFFFFFFF),
    surface = Color(0xFF070A12),
    onSurface = Color(0xFFFFFFFF),
    surfaceVariant = Color(0xFF111827),
    onSurfaceVariant = Color(0xFFF4F7FF),
    outline = Color(0xFFF4F7FF),
    outlineVariant = Color(0xFFBAC2DE),
    inverseSurface = Color(0xFFFFFFFF),
    inverseOnSurface = Color(0xFF05070D),
    inversePrimary = Mocha.Wizard,
    surfaceDim = Color(0xFF05070D),
    surfaceBright = Color(0xFF172033),
    surfaceContainerLowest = Color(0xFF05070D),
    surfaceContainerLow = Color(0xFF070A12),
    surfaceContainer = Color(0xFF0C111D),
    surfaceContainerHigh = Color(0xFF111827),
    surfaceContainerHighest = Color(0xFF172033)
)

data class ClearCutSemanticColors(
    val mode: AppearanceMode,
    val highContrast: Boolean,
    val background: Color,
    val backgroundMid: Color,
    val panel: Color,
    val panelRaised: Color,
    val panelHighest: Color,
    val cardStroke: Color,
    val cardStrokeStrong: Color,
    val text: Color,
    val subtext: Color,
    val subtextStrong: Color,
    val disabledText: Color,
    val accent: Color,
    val accentSecondary: Color,
    val success: Color,
    val warning: Color,
    val danger: Color,
    val focusRing: Color,
    val canvas: Color,
    val selectedSurface: Color,
    val disabledSurface: Color,
    val surfaceBase: Color,
    val surfaceLow: Color,
    val surface: Color,
    val surfaceHigh: Color,
    val overlay: Color,
    val overlayStrong: Color,
    val onAccent: Color,
)

val LocalClearCutColors = staticCompositionLocalOf {
    ClearCutThemeDefaults.colorsFor(AppearanceMode.DARK)
}

object ClearCutThemeDefaults {
    /**
     * ClearCut intentionally ships dark schemes only. Each selectable appearance mode
     * resolves to its own implemented scheme; there is no unsupported system-following
     * or light-mode branch hidden behind the settings control.
     */
    fun resolveMode(mode: AppearanceMode): AppearanceMode = mode

    fun colorSchemeFor(resolvedMode: AppearanceMode) = when (resolvedMode) {
        AppearanceMode.HIGH_CONTRAST_DARK -> ClearCutHighContrastColorScheme
        AppearanceMode.DARK -> ClearCutDarkColorScheme
    }

    fun colorsFor(resolvedMode: AppearanceMode): ClearCutSemanticColors = when (resolvedMode) {
        AppearanceMode.HIGH_CONTRAST_DARK -> ClearCutSemanticColors(
            mode = resolvedMode,
            highContrast = true,
            background = Color(0xFF05070D),
            backgroundMid = Color(0xFF070A12),
            panel = Color(0xFF070A12),
            panelRaised = Color(0xFF0C111D),
            panelHighest = Color(0xFF172033),
            cardStroke = Color(0xFFBAC2DE),
            cardStrokeStrong = Color(0xFFF4F7FF),
            text = Color(0xFFFFFFFF),
            subtext = Color(0xFFF4F7FF),
            subtextStrong = Color(0xFFFFFFFF),
            disabledText = Color(0xFFBAC2DE),
            accent = Mocha.Sky,
            accentSecondary = Mocha.Peach,
            success = Mocha.Green,
            warning = Mocha.Peach,
            danger = Mocha.Red,
            focusRing = Color(0xFFFFFFFF),
            canvas = Color(0xFF000000),
            selectedSurface = Mocha.Sky,
            disabledSurface = Color(0xFF111827),
            surfaceBase = Color(0xFF0C111D),
            surfaceLow = Color(0xFF172033),
            surface = Color(0xFF24324A),
            surfaceHigh = Color(0xFF24324A),
            overlay = Color(0xFFBAC2DE),
            overlayStrong = Color(0xFFF4F7FF),
            onAccent = Color(0xFF05070D),
        )
        AppearanceMode.DARK -> ClearCutSemanticColors(
            mode = AppearanceMode.DARK,
            highContrast = false,
            background = Mocha.Midnight,
            backgroundMid = Mocha.Mantle,
            panel = Mocha.Panel,
            panelRaised = Mocha.PanelRaised,
            panelHighest = Mocha.PanelHighest,
            cardStroke = Mocha.CardStroke,
            cardStrokeStrong = Mocha.CardStrokeStrong,
            text = Mocha.Text,
            subtext = Mocha.Subtext0,
            subtextStrong = Mocha.Subtext1,
            disabledText = Mocha.Subtext0,
            accent = Mocha.Sky,
            accentSecondary = Mocha.Peach,
            success = Mocha.Green,
            warning = Mocha.Peach,
            danger = Mocha.Red,
            focusRing = Mocha.Sky,
            canvas = Color(0xFF000000),
            selectedSurface = Mocha.Sky.copy(alpha = 0.14f),
            disabledSurface = Mocha.PanelHighest.copy(alpha = 0.48f),
            surfaceBase = Mocha.Base,
            surfaceLow = Mocha.Surface0,
            surface = Mocha.Surface1,
            surfaceHigh = Mocha.Surface2,
            overlay = Mocha.Overlay0,
            overlayStrong = Mocha.Overlay1,
            onAccent = AfuColors.text,
        )
    }

    fun contrastRatio(foreground: Color, background: Color): Double {
        val fg = relativeLuminance(foreground)
        val bg = relativeLuminance(background)
        val lighter = maxOf(fg, bg)
        val darker = minOf(fg, bg)
        return (lighter + 0.05) / (darker + 0.05)
    }

    private fun relativeLuminance(color: Color): Double {
        val r = linearizedChannel(color.red)
        val g = linearizedChannel(color.green)
        val b = linearizedChannel(color.blue)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    }

    private fun linearizedChannel(channel: Float): Double {
        val srgb = channel.toDouble()
        return if (srgb <= 0.03928) {
            srgb / 12.92
        } else {
            Math.pow((srgb + 0.055) / 1.055, 2.4)
        }
    }
}

private val ClearCutFontFamily = FontFamily.SansSerif

// Material3 default type scale; only the font family is set to SansSerif.
private val ClearCutTypography = Typography().let { base ->
    Typography(
        displayLarge = base.displayLarge.copy(fontFamily = ClearCutFontFamily),
        displayMedium = base.displayMedium.copy(fontFamily = ClearCutFontFamily),
        displaySmall = base.displaySmall.copy(fontFamily = ClearCutFontFamily),
        headlineLarge = base.headlineLarge.copy(fontFamily = ClearCutFontFamily),
        headlineMedium = base.headlineMedium.copy(fontFamily = ClearCutFontFamily),
        headlineSmall = base.headlineSmall.copy(fontFamily = ClearCutFontFamily),
        titleLarge = base.titleLarge.copy(fontFamily = ClearCutFontFamily),
        titleMedium = base.titleMedium.copy(fontFamily = ClearCutFontFamily),
        titleSmall = base.titleSmall.copy(fontFamily = ClearCutFontFamily),
        bodyLarge = base.bodyLarge.copy(fontFamily = ClearCutFontFamily),
        bodyMedium = base.bodyMedium.copy(fontFamily = ClearCutFontFamily),
        bodySmall = base.bodySmall.copy(fontFamily = ClearCutFontFamily),
        labelLarge = base.labelLarge.copy(fontFamily = ClearCutFontFamily),
        labelMedium = base.labelMedium.copy(fontFamily = ClearCutFontFamily),
        labelSmall = base.labelSmall.copy(fontFamily = ClearCutFontFamily),
    )
}

private val ClearCutShapes = Shapes(
    extraSmall = RoundedCornerShape(Radius.xs),
    small = RoundedCornerShape(Radius.sm),
    medium = RoundedCornerShape(Radius.md),
    large = RoundedCornerShape(Radius.xl),
    extraLarge = RoundedCornerShape(Radius.xxl),
)

@Composable
fun ClearCutTheme(
    appearanceMode: AppearanceMode = AppearanceMode.DARK,
    content: @Composable () -> Unit
) {
    val resolvedMode = ClearCutThemeDefaults.resolveMode(appearanceMode)
    CompositionLocalProvider(LocalClearCutColors provides ClearCutThemeDefaults.colorsFor(resolvedMode)) {
        MaterialTheme(
            colorScheme = ClearCutThemeDefaults.colorSchemeFor(resolvedMode),
            typography = ClearCutTypography,
            shapes = ClearCutShapes,
            content = content
        )
    }
}
