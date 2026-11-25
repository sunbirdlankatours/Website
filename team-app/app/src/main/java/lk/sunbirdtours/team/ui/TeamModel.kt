package lk.sunbirdtours.team.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import lk.sunbirdtours.team.TeamApp
import lk.sunbirdtours.team.data.ApiError
import lk.sunbirdtours.team.data.Chat
import lk.sunbirdtours.team.data.Live
import lk.sunbirdtours.team.data.Me
import lk.sunbirdtours.team.data.Message
import lk.sunbirdtours.team.ring.Rings

/** Everything the screens show, kept up to date from the inquiry box and its live line. */
class TeamModel(application: Application) : AndroidViewModel(application) {
    private val team = application as TeamApp
    private val api = team.api
    private val live = team.live

    var me by mutableStateOf(team.store.me()); private set
    var chats by mutableStateOf<List<Chat>>(emptyList()); private set
    var closedView by mutableStateOf(false); private set
    var loading by mutableStateOf(false); private set
    var busy by mutableStateOf(false); private set
    /** a sentence for the bar at the bottom of the screen */
    var problem by mutableStateOf<String?>(null)
    /** who is typing in which chat: "" = the traveller, otherwise a team member's name */
    var typing by mutableStateOf<Map<Long, String>>(emptyMap()); private set
    val liveOpen = live.open

    // the chat on screen
    var openId by mutableStateOf(0L); private set
    var open by mutableStateOf<Chat?>(null); private set
    var messages by mutableStateOf<List<Message>>(emptyList()); private set
    var draft by mutableStateOf(""); private set
    var sending by mutableStateOf(false); private set

    private val typingJobs = mutableMapOf<Long, Job>()
    private var typedAt = 0L
    private var front = false

    init {
        viewModelScope.launch { live.events.collect { heard(it) } }
    }

    // ------------------------------------------------------------------ signing in and out
    fun signIn(email: String, password: String) {
        if (busy) return
        busy = true
        viewModelScope.launch {
            try {
                me = api.login(email, password)
                team.registerPhone()
                if (front) live.start()
                refresh()
            } catch (e: Exception) {
                problem = e.message
            } finally {
                busy = false
            }
        }
    }

    fun signOut() {
        viewModelScope.launch {
            try { api.logout() } catch (e: Exception) { /* signed out here anyway */ }
            forget()
        }
    }

    private fun forget() {
        live.stop()
        team.store.clear()
        me = null
        chats = emptyList()
        closeChat()
    }

    /** the app came to the front (or went behind): a live line only while it's on screen */
    fun foreground(on: Boolean) {
        front = on
        TeamApp.inFront = on
        if (!on) { live.stop(); return }
        if (me == null) return
        live.start()
        refresh()
        if (openId != 0L) reload()
    }

    // ------------------------------------------------------------------ the list
    fun showClosed(on: Boolean) {
        if (on == closedView) return
        closedView = on
        chats = emptyList()
        refresh()
    }

    fun refresh() {
        if (me == null) return
        viewModelScope.launch {
            loading = true
            try {
                chats = api.chats(closedView).items
            } catch (e: Exception) {
                trouble(e)
            } finally {
                loading = false
            }
        }
    }

    private fun keep(c: Chat) {
        val fits = (c.status == "closed") == closedView
        val rest = chats.filter { it.id != c.id }
        chats = if (fits) (rest + c).sortedByDescending { it.updated } else rest
        if (c.id == openId) open = c
    }

    // ------------------------------------------------------------------ one chat
    fun openChat(id: Long) {
        openId = id
        open = chats.find { it.id == id }
        messages = emptyList()
        draft = ""
        TeamApp.viewing = id
        Rings.hush(team, id)
        reload()
    }

    fun closeChat() {
        if (openId != 0L) typed(openId, false)
        openId = 0L
        open = null
        messages = emptyList()
        draft = ""
        TeamApp.viewing = 0L
    }

    private fun reload() {
        val id = openId
        viewModelScope.launch {
            try {
                val d = api.chat(id)
                if (openId != id) return@launch
                open = d.chat
                messages = d.messages
                keep(d.chat)
                if (d.chat.unread > 0) markRead(id)
            } catch (e: Exception) {
                if (e is ApiError && e.status == 404) { problem = "That chat isn't there any more."; closeChat() } else trouble(e)
            }
        }
    }

    private fun markRead(id: Long) {
        viewModelScope.launch {
            try { api.markRead(id) } catch (e: Exception) { /* not worth a message */ }
        }
    }

    fun write(text: String) {
        draft = text
        val now = System.currentTimeMillis()
        if (text.isBlank()) typed(openId, false)
        else if (now - typedAt > 3_000) { typedAt = now; live.typing(openId, true) }
    }

    private fun typed(chat: Long, on: Boolean) {
        if (!on && typedAt == 0L) return
        if (!on) typedAt = 0L
        live.typing(chat, on)
    }

    fun send() {
        val text = draft.trim()
        val id = openId
        if (text.isEmpty() || sending || id == 0L) return
        sending = true
        viewModelScope.launch {
            try {
                add(api.reply(id, text))
                if (openId == id) draft = ""
                typed(id, false)
            } catch (e: Exception) {
                trouble(e)
            } finally {
                sending = false
            }
        }
    }

    private fun add(m: Message) {
        if (messages.any { it.id == m.id }) return
        messages = (messages + m).sortedBy { it.id }
    }

    fun setClosed(closed: Boolean) {
        val id = openId
        viewModelScope.launch {
            try {
                api.setStatus(id, if (closed) "closed" else "open")
                problem = if (closed) "Chat closed. It opens again if the traveller writes." else "Chat opened again."
                closeChat()
                refresh()
            } catch (e: Exception) {
                trouble(e)
            }
        }
    }

    fun delete() {
        val id = openId
        viewModelScope.launch {
            try {
                api.delete(id)
                chats = chats.filter { it.id != id }
                closeChat()
                problem = "Chat deleted."
            } catch (e: Exception) {
                trouble(e)
            }
        }
    }

    fun testRing() {
        viewModelScope.launch {
            try {
                val n = api.testRing()
                problem = if (n == 1) "Test ring sent. Your phone should ring now." else "Test ring sent to your $n phones."
            } catch (e: Exception) {
                trouble(e)
            }
        }
    }

    // ------------------------------------------------------------------ the live line
    private fun heard(e: Live.Event) {
        when (e) {
            is Live.Event.Said -> {
                e.summary?.let { keep(it) }
                if (e.chat == openId) {
                    add(e.message)
                    if (!e.message.fromTeam) {
                        stopTyping(e.chat)
                        if (front) markRead(e.chat) // read on screen: the other phones stop
                    }
                }
            }
            is Live.Event.Changed -> keep(e.summary)
            is Live.Event.Gone -> {
                chats = chats.filter { it.id != e.chat }
                if (e.chat == openId) { closeChat(); problem = "That chat was deleted." }
            }
            is Live.Event.Typing -> {
                if (e.member != 0L && e.member == me?.id) return
                if (e.on) {
                    typing = typing + (e.chat to (if (e.who == "visitor") "" else e.name))
                    typingJobs.remove(e.chat)?.cancel()
                    typingJobs[e.chat] = viewModelScope.launch { delay(6_000); stopTyping(e.chat) }
                } else stopTyping(e.chat)
            }
            Live.Event.Back -> { // caught up after the line was down
                refresh()
                if (openId != 0L) reload()
            }
            Live.Event.SignedOut -> {
                forget()
                problem = "You've been signed out. Please sign in again."
            }
        }
    }

    private fun stopTyping(chat: Long) {
        typingJobs.remove(chat)?.cancel()
        if (chat in typing) typing = typing - chat
    }

    private fun trouble(e: Exception) {
        if (e is ApiError && e.signIn) {
            forget()
            problem = "Your sign-in has ended. Please sign in again."
        } else {
            problem = e.message ?: "Something went wrong. Please try again."
        }
    }
}
