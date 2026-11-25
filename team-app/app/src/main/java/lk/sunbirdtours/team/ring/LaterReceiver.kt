package lk.sunbirdtours.team.ring

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** "Decline" on the call banner: this phone stops ringing and keeps a quiet reminder; the others keep ringing. */
class LaterReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        Rings.later(
            context,
            intent.getLongExtra("chat", 0L),
            intent.getStringExtra("title") ?: "A traveller",
            intent.getStringExtra("text") ?: "",
        )
    }
}
