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
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Email
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import lk.sunbirdtours.team.R
import lk.sunbirdtours.team.ring.Rings

/**
 * The app's one screen: Chats and Inquiries, with tabs at the bottom. Opened normally, it starts with the logo
 * animation (Intro). Opened from a ring (Answer, tapping the ring or its reminder), or opened while a chat is
 * ringing, it goes straight to that chat instead; from an inquiry notification, straight to Inquiries.
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
        val inquiry = intent?.hasExtra("inquiry") == true // from the new-inquiries notification
        intro = savedInstanceState == null && asked == 0L && ringing == 0L && !inquiry
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
        if (i?.hasExtra("inquiry") == true && model.me != null) {
            model.closeChat()
            model.openInquiry(i.getLongExtra("inquiry", 0L))
        }
        i?.removeExtra("chat")
        i?.removeExtra("inquiry")
    }

    companion object {
        /** opens the app straight into a chat (from a ring, its reminder, or the call screen's Answer) */
        fun openChat(c: Context, chat: Long): Intent = Intent(c, MainActivity::class.java)
            .putExtra("chat", chat)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)

        /** opens the app at Inquiries: one inquiry, or the list with 0 (from the new-inquiries notification) */
        fun openInquiry(c: Context, inquiry: Long): Intent = Intent(c, MainActivity::class.java)
            .putExtra("inquiry", inquiry)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP)
    }
}

@Composable
private fun Screens(m: TeamModel) {
    val bar = remember { SnackbarHostState() }
    LaunchedEffect(m.problem) {
        val p = m.problem ?: return@LaunchedEffect
        // cleared only after it has shown: clearing it first restarted this and closed the bar at once
        bar.showSnackbar(p, duration = if (p.length > 60) SnackbarDuration.Long else SnackbarDuration.Short)
        if (m.problem == p) m.problem = null
    }
    when {
        m.me == null -> SignInScreen(m, bar)
        m.openId != 0L -> {
            BackHandler { m.closeChat() }
            ChatScreen(m, bar)
        }
        m.inquiryId != 0L -> {
            BackHandler { m.closeInquiry() }
            InquiryScreen(m, bar)
        }
        else -> Tabs(m, bar)
    }
}

/** Chats and Inquiries, with the number of new inquiries on the Inquiries tab (as on the app icon) */
@Composable
private fun Tabs(m: TeamModel, bar: SnackbarHostState) {
    if (m.tab == Tab.INQUIRIES) BackHandler { m.tab = Tab.CHATS }
    Column(Modifier.fillMaxSize()) {
        Box(Modifier.weight(1f)) {
            if (m.tab == Tab.CHATS) ChatsScreen(m, bar) else InquiriesScreen(m, bar)
        }
        val colors = NavigationBarItemDefaults.colors(
            selectedIconColor = Navy, selectedTextColor = Navy, indicatorColor = Color(0xFFDCEBF7),
            unselectedIconColor = Muted, unselectedTextColor = Muted,
        )
        NavigationBar(containerColor = Color.White) {
            NavigationBarItem(
                selected = m.tab == Tab.CHATS, onClick = { m.tab = Tab.CHATS }, colors = colors,
                icon = { Icon(painterResource(R.drawable.ic_tab_chat), contentDescription = null) },
                label = { Text("Chats") },
            )
            NavigationBarItem(
                selected = m.tab == Tab.INQUIRIES, onClick = { m.tab = Tab.INQUIRIES; m.refreshInquiries() }, colors = colors,
                icon = {
                    BadgedBox(badge = {
                        if (m.newInquiries > 0) Badge(containerColor = Yellow, contentColor = Navy) {
                            Text(m.newInquiries.toString(), fontWeight = FontWeight.Bold)
                        }
                    }) { Icon(Icons.Filled.Email, contentDescription = null) }
                },
                label = { Text("Inquiries") },
            )
        }
    }
}
