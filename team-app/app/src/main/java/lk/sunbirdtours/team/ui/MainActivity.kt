package lk.sunbirdtours.team.ui

import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import lk.sunbirdtours.team.ring.Rings

/**
 * The app's one screen. Opened normally, it starts with the logo animation (Intro). Opened from a ring (Answer,
 * tapping the ring or its reminder), or opened while a chat is ringing, it goes straight to that chat instead.
 */
class MainActivity : ComponentActivity() {
    private val model: TeamModel by viewModels()
    private var intro by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // the animation only for a fresh, ordinary start: not after turning the phone, and not when a chat waits
        val ringing = Rings.ringingChat(this)
        val asked = chatFrom(intent)   // from a ring, its reminder, or Answer
        intro = savedInstanceState == null && asked == 0L && ringing == 0L
        openFrom(intent)
        if (asked == 0L && ringing > 0 && model.me != null) model.openChat(ringing) // its first frame is the chat
        setContent {
            SunbirdTheme {
                Crossfade(targetState = intro, animationSpec = tween(380), label = "intro") { showing ->
                    if (showing) Intro { intro = false } else Screens(model)
                }
            }
        }
    }

    // a ring was tapped or answered while the app was already open
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        intro = false
        openFrom(intent)
    }

    override fun onStart() {
        super.onStart()
        model.foreground(true)
    }

    // coming back to the app while a chat is ringing: straight into that chat
    override fun onResume() {
        super.onResume()
        val ringing = Rings.ringingChat(this)
        if (ringing > 0 && model.me != null) {
            intro = false
            model.openChat(ringing)
        }
    }

    override fun onStop() {
        model.foreground(false)
        super.onStop()
    }

    private fun chatFrom(i: Intent?): Long = i?.getLongExtra("chat", 0L) ?: 0L

    private fun openFrom(i: Intent?) {
        val chat = chatFrom(i)
        if (chat > 0 && model.me != null) model.openChat(chat)
        i?.removeExtra("chat")
    }

    companion object {
        /** opens the app straight into a chat (from a ring, its reminder, or the call screen's Answer) */
        fun openChat(c: Context, chat: Long): Intent = Intent(c, MainActivity::class.java)
            .putExtra("chat", chat)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)
    }
}

@Composable
private fun Screens(m: TeamModel) {
    val bar = remember { SnackbarHostState() }
    LaunchedEffect(m.problem) {
        val p = m.problem ?: return@LaunchedEffect
        m.problem = null
        bar.showSnackbar(p)
    }
    when {
        m.me == null -> SignInScreen(m, bar)
        m.openId != 0L -> {
            BackHandler { m.closeChat() }
            ChatScreen(m, bar)
        }
        else -> ChatsScreen(m, bar)
    }
}
