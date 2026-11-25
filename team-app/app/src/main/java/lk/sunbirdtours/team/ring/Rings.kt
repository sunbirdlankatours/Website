package lk.sunbirdtours.team.ring

import android.annotation.SuppressLint
import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull
import lk.sunbirdtours.team.R
import lk.sunbirdtours.team.TeamApp
import lk.sunbirdtours.team.ui.MainActivity

/**
 * Everything the phone shows and plays. The inquiry box sends a kind of ring (worker/src/ring.js):
 *   ring  a traveller started a chat: rings like a phone call until someone looks; after two minutes it
 *         becomes a quiet reminder
 *   ding  another message in a chat: one short sound
 *   hush  someone opened or answered that chat: stop
 *   test  "Send a test ring"
 * Each kind has its own channel, so the team can change its sound in Android's settings.
 */
object Rings {
    const val RING = "travellers"   // a new chat
    const val MESSAGE = "messages"  // more messages
    const val QUIET = "waiting"     // a chat still waiting, without sound
    private const val TAG = "chat"
    private const val RING_FOR_MS = 120_000L
    private const val BLUE = 0xFF1F74BA.toInt()

    fun channels(c: Context) {
        val ring = NotificationChannel(RING, "A traveller starts a chat", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Rings like a phone call when a traveller starts a chat on the website."
            setSound(
                RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE),
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build(),
            )
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 900, 700, 900, 700, 900)
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
        }
        val message = NotificationChannel(MESSAGE, "More messages in a chat", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "A short sound when a traveller writes again."
            enableVibration(true)
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
        }
        val quiet = NotificationChannel(QUIET, "Chats still waiting", NotificationManager.IMPORTANCE_LOW).apply {
            description = "A quiet reminder when nobody has picked up a new chat after two minutes."
            setSound(null, null)
        }
        c.getSystemService(NotificationManager::class.java).createNotificationChannels(listOf(ring, message, quiet))
    }

    /** What the inquiry box sent (from Firebase, or a test). Runs off the main thread: it may fetch the words. */
    fun handle(c: Context, kind: String, chat: Long) {
        when (kind) {
            "hush" -> hush(c, chat)
            "test" -> post(c, 0, "Test ring", "If you can hear this, chats will ring on this phone.", RING, insistent = true, timeoutMs = 12_000)
            "ring", "ding" -> {
                if (kind == "ding" && TeamApp.inFront && TeamApp.viewing == chat) return // being read right now
                val (title, text) = words(c, chat)
                if (kind == "ring") {
                    post(c, chat, title, text, RING, insistent = true)
                    later(c, chat, title, text)
                } else if (!ringing(c, chat)) {
                    post(c, chat, title, text, MESSAGE, insistent = false)
                }
            }
        }
    }

    /** The traveller's latest words, fetched from the inquiry box (they never go through Firebase). */
    private fun words(c: Context, chat: Long): Pair<String, String> = runBlocking {
        withTimeoutOrNull(5_000) {
            try {
                val d = TeamApp.of(c).api.chat(chat)
                val said = d.messages.lastOrNull { !it.fromTeam }?.text ?: d.chat.lastText
                (d.chat.flag + " " + d.chat.title).trim() to said
            } catch (e: Exception) {
                null
            }
        }
    } ?: ("A traveller is chatting" to "Open the app to answer.")

    fun hush(c: Context, chat: Long) {
        NotificationManagerCompat.from(c).cancel(TAG, chat.toInt())
        c.getSystemService(AlarmManager::class.java).cancel(quietIntent(c, chat, "", ""))
    }

    /** after two minutes, if nobody has looked, the ring stops and a quiet reminder stays */
    fun quiet(c: Context, chat: Long, title: String, text: String) {
        if (ringing(c, chat)) post(c, chat, title, "Still waiting: $text", QUIET, insistent = false)
    }

    private fun later(c: Context, chat: Long, title: String, text: String) {
        c.getSystemService(AlarmManager::class.java)
            .set(AlarmManager.ELAPSED_REALTIME, SystemClock.elapsedRealtime() + RING_FOR_MS, quietIntent(c, chat, title, text))
    }

    private fun quietIntent(c: Context, chat: Long, title: String, text: String): PendingIntent = PendingIntent.getBroadcast(
        c, chat.toInt(),
        Intent(c, QuietReceiver::class.java).putExtra("chat", chat).putExtra("title", title).putExtra("text", text),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    /** whether a ring for that chat is still showing */
    private fun ringing(c: Context, chat: Long): Boolean =
        c.getSystemService(NotificationManager::class.java).activeNotifications
            .any { it.tag == TAG && it.id == chat.toInt() && it.notification.channelId == RING }

    @SuppressLint("MissingPermission") // checked: areNotificationsEnabled
    private fun post(c: Context, chat: Long, title: String, text: String, channel: String, insistent: Boolean, timeoutMs: Long = 0) {
        val nm = NotificationManagerCompat.from(c)
        if (!nm.areNotificationsEnabled()) return
        val open = PendingIntent.getActivity(
            c, chat.toInt(),
            Intent(c, MainActivity::class.java).putExtra("chat", chat)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val b = NotificationCompat.Builder(c, channel)
            .setSmallIcon(R.drawable.ic_notify)
            .setColor(BLUE)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(open)
            .setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setPriority(if (channel == QUIET) NotificationCompat.PRIORITY_LOW else NotificationCompat.PRIORITY_HIGH)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setShowWhen(true)
        if (timeoutMs > 0) b.setTimeoutAfter(timeoutMs)
        val n = b.build()
        if (insistent) n.flags = n.flags or Notification.FLAG_INSISTENT // the sound repeats until someone looks
        nm.notify(TAG, chat.toInt(), n)
    }
}
