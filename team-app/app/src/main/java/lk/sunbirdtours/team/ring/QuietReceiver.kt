package lk.sunbirdtours.team.ring

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Two minutes after a ring (Rings.later): if nobody has looked, the ring becomes a quiet reminder. */
class QuietReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        Rings.quiet(
            context,
            intent.getLongExtra("chat", 0L),
            intent.getStringExtra("title") ?: "A traveller is chatting",
            intent.getStringExtra("text") ?: "",
        )
    }
}
