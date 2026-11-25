package lk.sunbirdtours.team.ui

import android.animation.ValueAnimator
import androidx.annotation.DrawableRes
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.Easing
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.widthIn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.GraphicsLayerScope
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import lk.sunbirdtours.team.R

/**
 * The opening animation when the app is opened normally: the emblem builds itself from its parts (res/drawable/
 * logo_part_*, made from the website's logo: only the emblem, no motto, no words), like the website's opening
 * screen. Opening the app from a ring skips it (MainActivity). A tap skips it too, and phones set to remove
 * animations don't get it.
 */
@Composable
fun Intro(onDone: () -> Unit) {
    val total = 1150f
    val t = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        if (!ValueAnimator.areAnimatorsEnabled()) { onDone(); return@LaunchedEffect }
        t.animateTo(total, tween(total.toInt(), easing = LinearEasing))
        delay(220)
        onDone()
    }
    // how far one move has got (0 to 1, eased) between two moments of the timeline, in ms
    fun step(from: Int, to: Int, ease: Easing = FastOutSlowInEasing): Float =
        ease.transform(((t.value - from) / (to - from)).coerceIn(0f, 1f))

    // the parts share the emblem's square canvas, with the ring's centre in the middle
    val centre = TransformOrigin(0.5f, 0.5f)
    val pop = CubicBezierEasing(0.34f, 1.56f, 0.64f, 1f)   // a little past, then back

    Box(
        Modifier.fillMaxSize().background(Paper)
            .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) { onDone() },
        contentAlignment = Alignment.Center,
    ) {
        Box(Modifier.fillMaxWidth(0.46f).widthIn(max = 240.dp).aspectRatio(1f)) {
            Part(R.drawable.logo_part_disc) {                // the white disc opens out
                val p = step(0, 480, pop); scaleX = 0.4f + 0.6f * p; scaleY = scaleX; alpha = step(0, 200); transformOrigin = centre
            }
            Part(R.drawable.logo_part_blue) {                // the blue, with the elephant, turns into place
                val p = step(120, 700, pop); scaleX = 0.6f + 0.4f * p; scaleY = scaleX; rotationZ = -50f * (1f - p)
                alpha = step(120, 320); transformOrigin = centre
            }
            Part(R.drawable.logo_part_sky) {                 // the light blue rises
                val p = step(320, 820); translationY = (1f - p) * size.height * 0.18f; alpha = p
            }
            Part(R.drawable.logo_part_bird) {                // the sunbird drops in and lands
                val p = step(560, 1060, pop); translationY = -(1f - p) * size.height * 0.45f; alpha = step(560, 700)
            }
        }
    }
}

@Composable
private fun Part(@DrawableRes id: Int, move: GraphicsLayerScope.() -> Unit) {
    Image(painterResource(id), contentDescription = null, modifier = Modifier.fillMaxSize().graphicsLayer(move))
}
