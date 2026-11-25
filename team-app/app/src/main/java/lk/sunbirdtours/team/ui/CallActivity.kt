package lk.sunbirdtours.team.ui

import android.app.KeyguardManager
import android.content.Intent
import android.graphics.Color as AndroidColor
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.addCallback
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animate
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import kotlin.math.abs
import kotlinx.coroutines.launch
import lk.sunbirdtours.team.R
import lk.sunbirdtours.team.ring.Call
import lk.sunbirdtours.team.ring.Rings

/**
 * The call screen: a traveller has started a chat. It shows over the lock screen and wakes the phone, like a phone
 * call. Swiping the yellow bubble up opens the chat at once (no opening animation); on a phone with a PIN, pattern or
 * fingerprint lock, Android asks to unlock first, so travellers' details stay private (the user's choice, 2026-11-25).
 * Later stops this phone ringing and keeps a quiet reminder, while the other phones keep ringing. It closes by itself
 * if someone else answers, or after two minutes.
 */
class CallActivity : ComponentActivity() {
    private var call by mutableStateOf<Call?>(null)
    private var tries by mutableIntStateOf(0) // goes up when the unlock was cancelled: the bubble drops back

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 27) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON)
        }
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(AndroidColor.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(AndroidColor.TRANSPARENT),
        )
        val c = Call.from(intent)
        // nothing to show, or the ring already ended (someone else answered before this opened)
        if (c == null || (c.chat > 0 && !Rings.ringing(this, c.chat))) { finish(); return }
        call = c
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.CREATED) { Rings.ended.collect { if (it == call?.chat) finish() } }
        }
        onBackPressedDispatcher.addCallback(this) { later() }
        setContent { SunbirdTheme { call?.let { CallScreen(it, tries, onAnswer = ::answer, onLater = ::later) } } }
    }

    // another chat rang while this one was showing: show the newest
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        Call.from(intent)?.let { call = it }
    }

    private fun answer() {
        val c = call ?: return
        if (c.chat == 0L) { later(); return } // the test ring: nothing to answer
        val go = {
            startActivity(MainActivity.openChat(this, c.chat))
            finish()
        }
        val lock = getSystemService(KeyguardManager::class.java)
        if (lock.isKeyguardLocked) {
            // the phone is locked: unlock first (fingerprint or PIN), then the chat
            lock.requestDismissKeyguard(this, object : KeyguardManager.KeyguardDismissCallback() {
                override fun onDismissSucceeded() { go() }
                override fun onDismissCancelled() { tries++ }
                override fun onDismissError() { tries++ }
            })
        } else go()
    }

    private fun later() {
        call?.let { Rings.later(this, it.chat, it.title, it.message) }
        finish()
    }
}

@Composable
private fun CallScreen(call: Call, tries: Int, onAnswer: () -> Unit, onLater: () -> Unit) {
    val pulse = rememberInfiniteTransition(label = "ringing")
    val wave by pulse.animateFloat(0f, 1f, infiniteRepeatable(tween(1800, easing = LinearEasing)), label = "wave")
    val test = call.chat == 0L

    BoxWithConstraints(Modifier.fillMaxSize().background(Navy)) {
        val short = maxHeight < 700.dp // a small phone: a smaller circle and less of the message
        val ring = if (short) 150.dp else 190.dp
        val face = ring * 0.62f
        Column(
            Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(horizontal = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // everything above the swipe: if it can't all fit, the end of the message is cut, never the swipe
            Column(Modifier.weight(1f).fillMaxWidth().clipToBounds(), horizontalAlignment = Alignment.CenterHorizontally) {
                Spacer(Modifier.height(if (short) 16.dp else 28.dp))
                Image(painterResource(R.drawable.logo_emblem), contentDescription = null, Modifier.size(44.dp))
                Spacer(Modifier.height(10.dp))
                Text(
                    if (test) "Test ring" else "New chat from the website",
                    color = Yellow, fontSize = 14.sp, fontWeight = FontWeight.Medium,
                )

                // the traveller, with rings going out like a phone call
                Spacer(Modifier.weight(0.6f))
                Box(Modifier.size(ring), contentAlignment = Alignment.Center) {
                    for (k in 0..1) {
                        val p = (wave + k * 0.5f) % 1f
                        Box(
                            Modifier.size(face).graphicsLayer { scaleX = 1f + p * 0.6f; scaleY = 1f + p * 0.6f; alpha = (1f - p) * 0.55f }
                                .border(2.dp, Sky, CircleShape),
                        )
                    }
                    Box(Modifier.size(face).clip(CircleShape).background(Blue), contentAlignment = Alignment.Center) {
                        Text(
                            call.title.trim().take(1).uppercase().ifBlank { "?" }, color = Color.White,
                            fontSize = if (short) 40.sp else 50.sp, fontWeight = FontWeight.SemiBold,
                        )
                    }
                }
                Spacer(Modifier.height(14.dp))
                Text(
                    call.title, color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.SemiBold,
                    textAlign = TextAlign.Center, maxLines = 2, overflow = TextOverflow.Ellipsis, lineHeight = 36.sp,
                )
                val about = listOf((call.flag + " " + call.country).trim(), call.contact).filter { it.isNotBlank() }.joinToString("  ·  ")
                if (about.isNotBlank()) {
                    Spacer(Modifier.height(6.dp))
                    Text(about, color = Color(0xFFB5D4F4), fontSize = 14.sp, textAlign = TextAlign.Center, maxLines = 2)
                }

                // what they wrote
                Spacer(Modifier.height(if (short) 16.dp else 22.dp))
                Surface(color = Color.White, shape = RoundedCornerShape(22.dp, 22.dp, 22.dp, 6.dp), modifier = Modifier.widthIn(max = 420.dp).fillMaxWidth()) {
                    Text(
                        call.message, Modifier.padding(horizontal = 18.dp, vertical = 14.dp), color = Navy, fontSize = 16.sp, lineHeight = 23.sp,
                        maxLines = if (short) 3 else 5, overflow = TextOverflow.Ellipsis,
                    )
                }
                if (call.page.isNotBlank()) {
                    Spacer(Modifier.height(8.dp))
                    Text("Writing from ${call.page}", color = Color(0xFF85B7EB), fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Spacer(Modifier.weight(1f))
            }

            // Later on the left, the swipe-up bubble in the middle, like an incoming phone call
            Row(Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 22.dp), verticalAlignment = Alignment.Bottom) {
                Box(Modifier.weight(1f).padding(bottom = 6.dp), contentAlignment = Alignment.BottomCenter) {
                    CallButton("Later", onClick = onLater)
                }
                SwipeUp(
                    hint = if (test) "Swipe up to stop the test" else "Swipe up to open the chat",
                    action = if (test) "Stop the test ring" else "Open the chat",
                    tries = tries, onDone = onAnswer,
                )
                Spacer(Modifier.weight(1f))
            }
        }
    }
}

/**
 * Swipe up to open the chat, like answering a phone call. The yellow bubble hops up now and then; drag it up past
 * the line and the chat opens, let go early and it drops back. A plain tap only makes it hop (so a pocket can't
 * answer); with TalkBack, a double-tap opens the chat.
 */
@Composable
private fun SwipeUp(hint: String, action: String, tries: Int, onDone: () -> Unit) {
    val density = LocalDensity.current
    val reach = with(density) { 170.dp.toPx() } // the furthest the bubble goes
    val enough = reach * 0.55f                    // let go above this and the chat opens
    var lift by remember { mutableFloatStateOf(0f) } // how far up the finger has taken the bubble, in px
    var held by remember { mutableStateOf(false) }
    var done by remember { mutableStateOf(false) }
    val hop = remember { Animatable(0f) }
    val haptics = LocalHapticFeedback.current
    val scope = rememberCoroutineScope()
    val idle = rememberInfiniteTransition(label = "swipe")
    val beat by idle.animateFloat(0f, 1f, infiniteRepeatable(tween(1700, easing = LinearEasing)), label = "beat")

    // the unlock (fingerprint or PIN) was cancelled: the bubble drops back to try again
    LaunchedEffect(tries) {
        if (tries > 0) {
            done = false
            animate(lift, 0f, animationSpec = spring(0.5f, Spring.StiffnessLow)) { v, _ -> lift = v }
        }
    }

    val drag = rememberDraggableState { dy ->
        val was = lift
        lift = (lift - dy).coerceIn(0f, reach)
        if (was < enough && lift >= enough) haptics.performHapticFeedback(HapticFeedbackType.GestureThresholdActivate)
    }
    val gone = (lift / enough).coerceIn(0f, 1f) // the hint and arrows fade as the bubble rises

    Column(Modifier.width(150.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            hint, color = Color(0xFFB5D4F4), fontSize = 13.sp, textAlign = TextAlign.Center, maxLines = 2,
            modifier = Modifier.graphicsLayer { alpha = 1f - gone },
        )
        Spacer(Modifier.height(6.dp))
        // three arrows, lighting up from the bottom, showing the way
        Canvas(Modifier.size(28.dp, 46.dp)) {
            val line = Stroke(width = 2.4.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round)
            for (k in 0..2) {
                val y = size.height - 8.dp.toPx() - k * 14.dp.toPx()
                val near = 1f - (abs(beat - 0.04f - k * 0.08f) / 0.14f).coerceIn(0f, 1f)
                val arrow = Path().apply {
                    moveTo(size.width * 0.18f, y + 4.dp.toPx()); lineTo(size.width / 2, y - 4.dp.toPx()); lineTo(size.width * 0.82f, y + 4.dp.toPx())
                }
                drawPath(arrow, Yellow.copy(alpha = (0.22f + 0.78f * near) * (1f - gone)), style = line)
            }
        }
        Spacer(Modifier.height(4.dp))
        Box(
            Modifier
                .graphicsLayer {
                    val rest = if (held || done || lift > 0f) 0f else bob(beat) * 12.dp.toPx()
                    translationY = -(lift + rest + hop.value * 34.dp.toPx())
                    val grow = 1f + 0.1f * (lift / reach)
                    scaleX = grow; scaleY = grow
                }
                .size(80.dp).clip(CircleShape).background(Yellow)
                .draggable(
                    drag, Orientation.Vertical, enabled = !done,
                    onDragStarted = { held = true },
                    onDragStopped = { speed ->
                        held = false
                        // far enough, or flicked up hard from part way
                        if (lift >= enough || (speed < -1800f && lift > reach * 0.25f)) {
                            done = true
                            animate(lift, reach, animationSpec = tween(140)) { v, _ -> lift = v }
                            onDone()
                        } else {
                            animate(lift, 0f, animationSpec = spring(0.45f, Spring.StiffnessMediumLow)) { v, _ -> lift = v }
                        }
                    },
                )
                .pointerInput(Unit) {
                    detectTapGestures {
                        scope.launch {
                            hop.animateTo(1f, tween(150, easing = FastOutSlowInEasing))
                            hop.animateTo(0f, spring(0.35f, Spring.StiffnessMediumLow))
                        }
                    }
                }
                .semantics {
                    role = Role.Button
                    contentDescription = action
                    onClick(label = action) { onDone(); true }
                },
            contentAlignment = Alignment.Center,
        ) { BubbleIcon(Navy) }
    }
}

/** the idle hop: up, down, a small second hop, then rest (t from 0 to 1 over one beat) */
private fun bob(t: Float): Float {
    fun e(x: Float) = FastOutSlowInEasing.transform(x.coerceIn(0f, 1f))
    return when {
        t < 0.16f -> e(t / 0.16f)
        t < 0.32f -> 1f - e((t - 0.16f) / 0.16f)
        t < 0.40f -> 0.3f * e((t - 0.32f) / 0.08f)
        t < 0.48f -> 0.3f * (1f - e((t - 0.40f) / 0.08f))
        else -> 0f
    }
}

@Composable
private fun CallButton(label: String, onClick: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            Modifier.size(64.dp).clip(CircleShape)
                .border(1.5.dp, Color(0xFFB5D4F4), CircleShape)
                .clickable(role = Role.Button, onClick = onClick)
                .semantics { contentDescription = label },
            contentAlignment = Alignment.Center,
        ) { LaterIcon(Color.White) }
        Spacer(Modifier.height(8.dp))
        Text(label, color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Medium)
    }
}

/** a chat bubble, on the swipe-up bubble */
@Composable
private fun BubbleIcon(color: Color) {
    Canvas(Modifier.size(32.dp)) {
        val w = size.width; val h = size.height
        drawRoundRect(color, Offset(w * 0.06f, h * 0.12f), Size(w * 0.88f, h * 0.62f), CornerRadius(w * 0.22f))
        val tail = Path().apply { moveTo(w * 0.24f, h * 0.68f); lineTo(w * 0.2f, h * 0.92f); lineTo(w * 0.46f, h * 0.72f); close() }
        drawPath(tail, color)
        for (k in 0..2) drawCircle(Yellow, radius = w * 0.055f, center = Offset(w * (0.32f + k * 0.18f), h * 0.43f))
    }
}

/** a clock, for Later */
@Composable
private fun LaterIcon(color: Color) {
    Canvas(Modifier.size(28.dp)) {
        val r = size.minDimension / 2 - 2.dp.toPx()
        val c = Offset(size.width / 2, size.height / 2)
        val line = Stroke(width = 2.4.dp.toPx(), cap = StrokeCap.Round)
        drawCircle(color, r, c, style = line)
        drawLine(color, c, Offset(c.x, c.y - r * 0.58f), strokeWidth = line.width, cap = StrokeCap.Round)
        drawLine(color, c, Offset(c.x + r * 0.42f, c.y + r * 0.2f), strokeWidth = line.width, cap = StrokeCap.Round)
    }
}
