package lk.sunbirdtours.team.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.delay
import lk.sunbirdtours.team.R
import lk.sunbirdtours.team.TeamApp
import lk.sunbirdtours.team.data.Chat
import lk.sunbirdtours.team.ring.Phone

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatsScreen(m: TeamModel, bar: SnackbarHostState) {
    val ctx = LocalContext.current
    val team = TeamApp.of(ctx)
    var menu by remember { mutableStateOf(false) }

    // "not connected", only once the live line has been down for a few seconds
    val liveOpen by m.liveOpen.collectAsStateWithLifecycle()
    var down by remember { mutableStateOf(false) }
    LaunchedEffect(liveOpen) { down = false; if (!liveOpen) { delay(6_000); down = true } }

    Scaffold(
        snackbarHost = { SnackbarHost(bar) },
        contentWindowInsets = WindowInsets(0, 0, 0, 0), // the tabs at the bottom take care of the bottom edge
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Chats", fontWeight = FontWeight.SemiBold, color = Navy)
                        Text("Signed in as ${m.me?.firstName ?: ""}", style = MaterialTheme.typography.bodySmall, color = Muted)
                    }
                },
                actions = {
                    IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, contentDescription = "More") }
                    DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                        if (team.ringsBuilt) {
                            DropdownMenuItem(text = { Text("Send a test ring") }, onClick = { menu = false; m.testRing() })
                            DropdownMenuItem(text = { Text("Test with the app closed") }, onClick = { menu = false; m.testRing(20) })
                        }
                        DropdownMenuItem(text = { Text("Ring sound") }, onClick = { menu = false; Phone.openRingSound(ctx) })
                        DropdownMenuItem(text = { Text("Refresh") }, onClick = { menu = false; m.refresh() })
                        HorizontalDivider()
                        DropdownMenuItem(text = { Text("Sign out") }, onClick = { menu = false; m.signOut() })
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Paper),
            )
        },
    ) { pad ->
        Column(Modifier.fillMaxSize().padding(pad)) {
            SetupCard(m) // what this phone still needs to ring with the app closed
            if (down) Note("Not connected to the inquiry box. Pull down to try again.", null) {}

            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth().padding(horizontal = Gap, vertical = 8.dp)) {
                SegmentedButton(
                    selected = !m.closedView, onClick = { m.showClosed(false) },
                    shape = SegmentedButtonDefaults.itemShape(0, 2),
                ) { Text("Open") }
                SegmentedButton(
                    selected = m.closedView, onClick = { m.showClosed(true) },
                    shape = SegmentedButtonDefaults.itemShape(1, 2),
                ) { Text("Closed") }
            }

            PullToRefreshBox(isRefreshing = m.loading, onRefresh = { m.refresh() }, modifier = Modifier.fillMaxSize()) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
                    if (m.chats.isEmpty() && !m.loading) item { Empty(m.closedView) }
                    items(m.chats, key = { it.id }) { c ->
                        ChatRow(c, m.typing[c.id], m.me?.id ?: 0L) { m.openChat(c.id) }
                        HorizontalDivider(Modifier.padding(start = 78.dp), color = Line)
                    }
                }
            }
        }
    }
}

@Composable
private fun ChatRow(c: Chat, typing: String?, me: Long, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = Gap, vertical = 12.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Box(
            Modifier.size(46.dp).clip(CircleShape).background(if (c.waiting) Yellow else Color(0xFFDCEBF7)),
            contentAlignment = Alignment.Center,
        ) {
            Text(c.flag.ifBlank { c.title.take(1).uppercase() }, fontSize = if (c.flag.isNotBlank()) 22.sp else 18.sp, color = Navy, fontWeight = FontWeight.SemiBold)
        }
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    c.title, Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis,
                    fontWeight = if (c.waiting) FontWeight.Bold else FontWeight.SemiBold, color = Ink, fontSize = 16.sp,
                )
                Text(shortWhen(c.updated), style = MaterialTheme.typography.bodySmall, color = if (c.waiting) Blue else Muted)
            }
            Spacer(Modifier.height(3.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                val line = when {
                    typing != null -> if (typing.isEmpty()) "typing…" else "$typing is typing…"
                    c.lastFrom == "team" -> (if (c.member == me) "You" else c.memberName.ifBlank { "Team" }) + ": " + c.lastText
                    else -> c.lastText
                }
                Text(
                    line, Modifier.weight(1f), maxLines = 2, overflow = TextOverflow.Ellipsis, fontSize = 14.sp,
                    color = if (typing != null) Blue else if (c.waiting) Ink else Muted,
                    fontStyle = if (typing != null) FontStyle.Italic else FontStyle.Normal,
                )
                if (c.unread > 0) {
                    Spacer(Modifier.width(8.dp))
                    Box(
                        Modifier.widthIn(min = 24.dp).height(24.dp).clip(CircleShape).background(Yellow).padding(horizontal = 7.dp),
                        contentAlignment = Alignment.Center,
                    ) { Text(c.unread.toString(), color = Navy, fontSize = 12.sp, fontWeight = FontWeight.Bold) }
                }
            }
            if (c.page.isNotBlank() || c.memberName.isNotBlank()) {
                Spacer(Modifier.height(3.dp))
                Text(
                    listOfNotNull(
                        c.page.takeIf { it.isNotBlank() },
                        c.memberName.takeIf { it.isNotBlank() }?.let { if (c.member == me) "you're answering" else "$it is answering" },
                    ).joinToString(" · "),
                    fontSize = 12.sp, color = Muted, maxLines = 1, overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun Empty(closed: Boolean) {
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 36.dp, vertical = 64.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Image(painterResource(R.drawable.logo_emblem), contentDescription = null, Modifier.size(64.dp).alpha(0.45f))
        Text(if (closed) "No closed chats" else "No open chats", fontWeight = FontWeight.SemiBold, color = Navy, fontSize = 17.sp)
        Text(
            if (closed) "Chats you close show here. They open again if the traveller writes."
            else "When a traveller writes in the chat on the website, this phone rings and the chat shows here.",
            color = Muted, textAlign = TextAlign.Center, fontSize = 14.sp,
        )
    }
}

/** a pale-yellow line across the top, like the notes in the website's chat card */
@Composable
fun Note(text: String, action: String?, onAction: () -> Unit) {
    Surface(color = Pale, shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth().padding(horizontal = Gap, vertical = 4.dp)) {
        Row(Modifier.padding(start = 14.dp, end = 6.dp, top = 6.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(text, Modifier.weight(1f).padding(vertical = 6.dp), fontSize = 13.sp, color = Navy)
            if (action != null) TextButton(onClick = onAction) { Text(action, fontWeight = FontWeight.Bold) }
        }
    }
}
