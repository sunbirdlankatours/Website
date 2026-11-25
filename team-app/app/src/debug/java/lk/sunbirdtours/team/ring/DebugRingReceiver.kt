package lk.sunbirdtours.team.ring

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import kotlin.concurrent.thread

/**
 * Test builds only: pretends Firebase rang, so the rings can be tried without it.
 *   adb shell am broadcast -a lk.sunbirdtours.team.DEBUG_RING -n lk.sunbirdtours.team/.ring.DebugRingReceiver --es kind ring --el chat 5
 */
class DebugRingReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val done = goAsync()
        thread {
            try {
                Rings.handle(context, intent.getStringExtra("kind") ?: "ring", intent.getLongExtra("chat", 0L))
            } finally {
                done.finish()
            }
        }
    }
}
