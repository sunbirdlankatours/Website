package lk.sunbirdtours.team.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// the website's colours (static/css/site.css)
val Blue = Color(0xFF1F74BA)
val Navy = Color(0xFF0C3460)
val Sky = Color(0xFF29ABE2)
val Yellow = Color(0xFFFBDC03)
val Paper = Color(0xFFFBF8F2)
val Ink = Color(0xFF1B2B36)
val Muted = Color(0xFF4A6170)
val Line = Color(0xFFE4E0D8)
val Pale = Color(0xFFFDF6CF)  // the chat card's notes
val Red = Color(0xFFB3402F)

@Composable
fun SunbirdTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Blue,
            onPrimary = Color.White,
            primaryContainer = Color(0xFFDCEBF7),
            onPrimaryContainer = Navy,
            secondary = Navy,
            onSecondary = Color.White,
            tertiary = Yellow,
            onTertiary = Navy,
            background = Paper,
            onBackground = Ink,
            surface = Paper,
            onSurface = Ink,
            surfaceVariant = Color(0xFFF1EDE5),
            onSurfaceVariant = Muted,
            surfaceContainer = Color.White,
            surfaceContainerHigh = Color.White,
            outline = Line,
            outlineVariant = Line,
            error = Red,
        ),
        content = content,
    )
}
