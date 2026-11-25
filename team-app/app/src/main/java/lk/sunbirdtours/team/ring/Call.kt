package lk.sunbirdtours.team.ring

import android.content.Context
import android.content.Intent
import lk.sunbirdtours.team.data.ChatDetail
import lk.sunbirdtours.team.ui.CallActivity

/** A ringing chat, as the call screen shows it. chat 0 is "Send a test ring". */
data class Call(
    val chat: Long,
    val title: String,    // the traveller's name
    val flag: String,
    val country: String,
    val contact: String,  // their email or WhatsApp number
    val message: String,  // what they wrote
    val page: String,     // where on the website
) {
    fun intent(c: Context): Intent = Intent(c, CallActivity::class.java)
        .putExtra("chat", chat).putExtra("title", title).putExtra("flag", flag).putExtra("country", country)
        .putExtra("contact", contact).putExtra("message", message).putExtra("page", page)

    fun laterIntent(c: Context): Intent = Intent(c, LaterReceiver::class.java)
        .putExtra("chat", chat).putExtra("title", title).putExtra("text", message)

    companion object {
        fun of(d: ChatDetail): Call {
            val ch = d.chat
            return Call(
                ch.id, ch.title, ch.flag, ch.countryName, ch.email.ifBlank { ch.whatsapp },
                d.messages.lastOrNull { !it.fromTeam }?.text ?: ch.lastText, ch.page,
            )
        }

        fun test() = Call(0, "Test ring", "", "", "", "If you can see and hear this, chats will ring on this phone like a call.", "")

        fun from(i: Intent?): Call? {
            if (i == null || !i.hasExtra("chat")) return null
            val s = { k: String -> i.getStringExtra(k) ?: "" }
            return Call(i.getLongExtra("chat", 0L), s("title"), s("flag"), s("country"), s("contact"), s("message"), s("page"))
        }
    }
}
