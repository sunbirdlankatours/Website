package lk.sunbirdtours.team.ui

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember

class MainActivity : ComponentActivity() {
    private val model: TeamModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        openFrom(intent)
        setContent { SunbirdTheme { Screens(model) } }
    }

    // a ring was tapped while the app was already open
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        openFrom(intent)
    }

    private fun openFrom(i: Intent?) {
        val chat = i?.getLongExtra("chat", 0L) ?: 0L
        if (chat > 0 && model.me != null) model.openChat(chat)
        i?.removeExtra("chat")
    }

    override fun onStart() {
        super.onStart()
        model.foreground(true)
    }

    override fun onStop() {
        model.foreground(false)
        super.onStop()
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
