package lk.sunbirdtours.team.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import lk.sunbirdtours.team.data.Chat
import lk.sunbirdtours.team.data.Message

/** a message, or the line that starts a new day */
private sealed interface Item {
    val key: String
    data class Day(val name: String) : Item { override val key get() = "day-$name" }
    data class Said(val m: Message) : Item { override val key get() = "m-${m.id}" }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(m: TeamModel, bar: SnackbarHostState) {
    val ctx = LocalContext.current
    val chat = m.open
    var menu by remember { mutableStateOf(false) }
    var asking by remember { mutableStateOf(false) }

    Scaffold(
        snackbarHost = { SnackbarHost(bar) },
        topBar = {
            TopAppBar(
                navigationIcon = {
                    IconButton(onClick = { m.closeChat() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back to chats") }
                },
                title = {
                    Column {
                        Text(
                            if (chat == null) "Chat" else (chat.flag + " " + chat.title).trim(),
                            maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.SemiBold, color = Navy,
                        )
                        val about = listOfNotNull(
                            chat?.countryName?.takeIf { it.isNotBlank() && chat.name.isNotBlank() },
                            chat?.page?.takeIf { it.isNotBlank() }?.let { "on $it" },
                            if (chat?.status == "closed") "closed" else null,
                        ).joinToString(" · ")
                        if (about.isNotBlank()) Text(about, style = MaterialTheme.typography.bodySmall, color = Muted, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                },
                actions = {
                    if (chat != null) {
                        IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, contentDescription = "More") }
                        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                            if (chat.status == "closed") DropdownMenuItem(text = { Text("Open again") }, onClick = { menu = false; m.setClosed(false) })
                            else DropdownMenuItem(text = { Text("Close chat") }, onClick = { menu = false; m.setClosed(true) })
                            HorizontalDivider()
                            DropdownMenuItem(text = { Text("Delete chat", color = Red) }, onClick = { menu = false; asking = true })
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Paper),
            )
        },
        bottomBar = { Write(m) },
    ) { pad ->
        Column(Modifier.fillMaxSize().padding(pad)) {
            if (chat != null && (chat.email.isNotBlank() || chat.whatsapp.isNotBlank())) Reach(ctx, chat, m.messages)
            val items = remember(m.messages) {
                val list = mutableListOf<Item>()
                var last: Message? = null
                for (msg in m.messages) {
                    if (last == null || !sameDay(last.at, msg.at)) list += Item.Day(dayName(msg.at))
                    list += Item.Said(msg)
                    last = msg
                }
                list.reversed() // the newest at the bottom (the list runs upwards)
            }
            val typing = m.typing[m.openId]
            LazyColumn(
                Modifier.weight(1f).fillMaxWidth(),
                reverseLayout = true,
                contentPadding = PaddingValues(horizontal = 14.dp, vertical = 10.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp, Alignment.Bottom), // a short chat sits by the reply box
            ) {
                if (typing != null) item(key = "typing") {
                    Text(
                        if (typing.isEmpty()) "The traveller is typing…" else "$typing is typing…",
                        color = Blue, fontStyle = FontStyle.Italic, fontSize = 13.sp, modifier = Modifier.padding(start = 6.dp),
                    )
                }
                items(items, key = { it.key }) {
                    when (it) {
                        is Item.Day -> DayLine(it.name)
                        is Item.Said -> Bubble(it.m)
                    }
                }
                if (m.messages.isEmpty()) item(key = "loading") {
                    Box(Modifier.fillMaxWidth().padding(40.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                }
            }
        }
    }

    if (asking) AlertDialog(
        onDismissRequest = { asking = false },
        title = { Text("Delete this chat?") },
        text = { Text("The whole chat is deleted for everyone on the team. This can't be undone.") },
        confirmButton = { TextButton(onClick = { asking = false; m.delete() }) { Text("Delete", color = Red) } },
        dismissButton = { TextButton(onClick = { asking = false }) { Text("Keep it") } },
    )
}

@Composable
private fun DayLine(name: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        HorizontalDivider(Modifier.weight(1f), color = Line)
        Text(name.uppercase(), Modifier.padding(horizontal = 12.dp), fontSize = 11.sp, letterSpacing = 2.sp, color = Muted, fontWeight = FontWeight.Bold)
        HorizontalDivider(Modifier.weight(1f), color = Line)
    }
}

@Composable
private fun Bubble(msg: Message) {
    val ours = msg.fromTeam
    Column(Modifier.fillMaxWidth(), horizontalAlignment = if (ours) Alignment.End else Alignment.Start) {
        Surface(
            color = if (ours) Blue else Color.White,
            contentColor = if (ours) Color.White else Ink,
            shape = RoundedCornerShape(20.dp, 20.dp, if (ours) 20.dp else 6.dp, if (ours) 6.dp else 20.dp),
            border = if (ours) null else BorderStroke(1.dp, Line),
            modifier = Modifier.widthIn(max = 300.dp),
        ) {
            SelectionContainer {
                Text(msg.text, Modifier.padding(horizontal = 15.dp, vertical = 10.dp), fontSize = 15.sp, lineHeight = 21.sp)
            }
        }
        Text(
            (if (ours) msg.name.ifBlank { "Team" } + " · " else "") + clock(msg.at),
            Modifier.padding(top = 4.dp, start = 8.dp, end = 8.dp), fontSize = 11.sp, color = Muted,
        )
    }
}

/** the email or WhatsApp number the traveller left, to answer them there */
@Composable
private fun Reach(ctx: Context, chat: Chat, messages: List<Message>) {
    Row(Modifier.fillMaxWidth().padding(horizontal = Gap, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        if (chat.email.isNotBlank()) AssistChip(
            onClick = {
                open(ctx, Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:" + chat.email))
                    .putExtra(Intent.EXTRA_SUBJECT, "Your chat with Sunbird Lanka Tours")
                    .putExtra(Intent.EXTRA_TEXT, "\n\n\n" + transcript(chat, messages)))
            },
            label = { Text(chat.email, maxLines = 1, overflow = TextOverflow.Ellipsis) },
            leadingIcon = { Icon(Icons.Filled.Email, contentDescription = null, Modifier.size(AssistChipDefaults.IconSize)) },
            modifier = Modifier.weight(1f, fill = false),
        )
        if (chat.whatsapp.isNotBlank()) AssistChip(
            onClick = { open(ctx, Intent(Intent.ACTION_VIEW, Uri.parse("https://wa.me/" + chat.whatsapp.filter { it.isDigit() }))) },
            label = { Text("WhatsApp " + chat.whatsapp, maxLines = 1) },
            leadingIcon = { Icon(Icons.Filled.Phone, contentDescription = null, Modifier.size(AssistChipDefaults.IconSize)) },
        )
    }
}

private fun open(ctx: Context, i: Intent) {
    try { ctx.startActivity(i) } catch (e: ActivityNotFoundException) { /* no app for it on this phone */ }
}

/** the reply box, with the yellow sun button to send */
@Composable
private fun Write(m: TeamModel) {
    Surface(color = Paper) {
        Row(
            Modifier.fillMaxWidth().navigationBarsPadding().imePadding().padding(start = 12.dp, end = 8.dp, top = 6.dp, bottom = 10.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            OutlinedTextField(
                value = m.draft, onValueChange = { m.write(it) },
                placeholder = { Text("Write a reply") },
                modifier = Modifier.weight(1f), maxLines = 5, shape = RoundedCornerShape(26.dp),
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = Color.White, unfocusedContainerColor = Color.White,
                    focusedBorderColor = Sky, unfocusedBorderColor = Line,
                ),
            )
            Spacer(Modifier.width(8.dp))
            val ready = m.draft.isNotBlank() && !m.sending
            IconButton(
                onClick = { m.send() }, enabled = ready,
                modifier = Modifier.padding(bottom = 4.dp).size(48.dp).clip(CircleShape),
                colors = IconButtonDefaults.iconButtonColors(
                    containerColor = Yellow, contentColor = Navy,
                    disabledContainerColor = Color(0xFFEEF1F2), disabledContentColor = Color(0xFF8D9EA8),
                ),
            ) {
                if (m.sending) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = Navy)
                else Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
            }
        }
    }
}

