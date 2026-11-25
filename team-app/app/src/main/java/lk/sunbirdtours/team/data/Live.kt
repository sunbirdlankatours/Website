package lk.sunbirdtours.team.data

import android.os.Handler
import android.os.Looper
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * The live line to the inquiry box's doorbell (worker/src/desk.js), open while the app is on screen: new
 * messages, changes and "typing" arrive the moment they happen. When the app is in the background, Firebase rings
 * the phone instead. If the line drops, it opens again by itself, a little later each time.
 */
class Live(private val api: Api, private val store: Store) {
    sealed interface Event {
        data class Said(val chat: Long, val message: Message, val summary: Chat?) : Event
        data class Changed(val summary: Chat) : Event
        data class Gone(val chat: Long) : Event
        data class Typing(val chat: Long, val who: String, val name: String, val member: Long, val on: Boolean) : Event
        /** the line has (re)opened: time to catch up on anything missed */
        data object Back : Event
        data object SignedOut : Event
    }

    private val _events = MutableSharedFlow<Event>(extraBufferCapacity = 64)
    val events: SharedFlow<Event> = _events
    private val _open = MutableStateFlow(false)
    val open: StateFlow<Boolean> = _open

    private val main = Handler(Looper.getMainLooper())
    private val client = api.http.newBuilder().readTimeout(0, TimeUnit.SECONDS).build()
    private var ws: WebSocket? = null
    private var wanted = false
    private var tries = 0
    @Volatile private var heard = 0L

    fun start() = main.post { wanted = true; connect() }

    fun stop() = main.post {
        wanted = false
        main.removeCallbacks(retry)
        main.removeCallbacks(ping)
        ws?.close(1000, null)
        ws = null
        _open.value = false
    }

    /** "typing" in a chat, for the traveller and the rest of the team */
    fun typing(chat: Long, on: Boolean) {
        ws?.send(JSONObject().put("t", "typing").put("chat", chat).put("on", on).toString())
    }

    private val retry = Runnable { connect() }

    // a "ping" every 30 s keeps the line open (the doorbell answers "pong" without waking); no answer for a while
    // means the line is dead, so it's dropped and opened again
    private val ping = object : Runnable {
        override fun run() {
            val s = ws ?: return
            if (System.currentTimeMillis() - heard > 75_000) { s.cancel(); return }
            s.send("ping")
            main.postDelayed(this, 30_000)
        }
    }

    private fun connect() {
        if (!wanted || ws != null) return
        val token = store.token ?: return
        heard = System.currentTimeMillis()
        val req = Request.Builder().url(api.base + "/api/chat/live").header("Authorization", "Bearer $token").build()
        ws = client.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                heard = System.currentTimeMillis()
                webSocket.send("ping") // a line that has said something closes cleanly later
                main.post {
                    if (ws !== webSocket) return@post
                    tries = 0
                    _open.value = true
                    main.removeCallbacks(ping)
                    main.postDelayed(ping, 30_000)
                    _events.tryEmit(Event.Back)
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                heard = System.currentTimeMillis()
                if (text == "pong") return
                val m = try { JSONObject(text) } catch (e: Exception) { return }
                val e: Event? = when (m.optString("t")) {
                    "message" -> Event.Said(
                        m.optLong("chat"), m.getJSONObject("message").toMessage(),
                        m.optJSONObject("summary")?.toChat(),
                    )
                    "chat" -> m.optJSONObject("summary")?.let { Event.Changed(it.toChat()) }
                    "gone" -> Event.Gone(m.optLong("chat"))
                    "typing" -> Event.Typing(m.optLong("chat"), m.optString("who"), m.optString("name"), m.optLong("member"), m.optBoolean("on"))
                    "bye" -> {
                        webSocket.close(1000, null)
                        if (m.optString("why") == "signed out") Event.SignedOut else null
                    }
                    else -> null
                }
                if (e != null) _events.tryEmit(e)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                main.post { lost(webSocket, code) }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                main.post { lost(webSocket, response?.code ?: 0) }
            }
        })
    }

    private fun lost(w: WebSocket, code: Int) {
        if (ws !== w) return
        ws = null
        _open.value = false
        main.removeCallbacks(ping)
        if (!wanted) return
        if (code == 401 || code == 4001) { // the sign-in has ended: no point trying again
            _events.tryEmit(Event.SignedOut)
            return
        }
        tries++
        main.postDelayed(retry, minOf(60_000L, 2_000L shl minOf(tries, 5)))
    }
}
