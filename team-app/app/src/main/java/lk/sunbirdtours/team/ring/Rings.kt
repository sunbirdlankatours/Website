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
import android.os.Build
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.Person
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull
import lk.sunbirdtours.team.R
import lk.sunbirdtours.team.TeamApp
import lk.sunbirdtours.team.ui.CallActivity
import lk.sunbirdtours.team.ui.MainActivity

/**
 * Everything the phone shows and plays. The inquiry box sends a kind of ring (worker/src/ring.js):
 *   ring  a traveller started a chat: rings like a phone call. A locked or sleeping phone shows the call screen
 *         (CallActivity); a phone in use shows a call banner with Answer and Decline. After two minutes it
 *         becomes a quiet reminder.
 *   ding  another message in a chat: one short sound
 *   hush  someone opened or answered that chat: stop, and close the call screen
 *   test  "Send a test ring": the call screen, with nothing to answer
 * Each kind has its own channel, so the team can change its sound in Android's settings.
 */
object Rings {
    const val RING = "travellers"   // a new chat
    const val RING_HERE = "travellers_here" // a new chat while the app is open: the same ring, without Android's banner
    const val MESSAGE = "messages"  // more messages
    const val QUIET = "waiting"     // a chat still waiting, without sound
    private const val TAG = "chat"
    private const val RING_FOR_MS = 120_000L
    private const val BLUE = 0xFF1F74BA.toInt()
    private val RINGS = setOf(RING, RING_HERE)

    /** chats whose ring has ended here (answered, hushed, later, or gone quiet): the call screen closes */
    private val _ended = MutableSharedFlow<Long>(extraBufferCapacity = 16)
    val ended: SharedFlow<Long> = _ended

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
        // the app's own call screen covers it, so no banner over the top (default importance: sound, no banner)
        val here = NotificationChannel(RING_HERE, "A traveller starts a chat (app open)", NotificationManager.IMPORTANCE_DEFAULT).apply {
            description = "The same ring, when the app is already open and shows the call itself."
            setSound(ring.sound, ring.audioAttributes)
            enableVibration(true)
            vibrationPattern = ring.vibrationPattern
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
        c.getSystemService(NotificationManager::class.java).createNotificationChannels(listOf(ring, here, message, quiet))
    }

    /** Whether Android lets a ring take over the screen like a phone call (Android 14 and later can say no). */
    fun canTakeOverScreen(c: Context): Boolean =
        Build.VERSION.SDK_INT < 34 || c.getSystemService(NotificationManager::class.java).canUseFullScreenIntent()

    /** What the inquiry box sent (from Firebase, or a test). Runs off the main thread: it fetches the words. */
    fun handle(c: Context, kind: String, chat: Long) {
        when (kind) {
            "hush" -> hush(c, chat)
            "test" -> ring(c, Call.test())
            "ring" -> ring(c, fetch(c, chat))
            "ding" -> {
                if (TeamApp.inFront && TeamApp.viewing == chat) return // being read right now
                if (ringing(c, chat)) return                             // still ringing: that's enough
                val call = fetch(c, chat)
                post(c, chat, call.title, call.message, MESSAGE)
            }
        }
    }

    /** The traveller and their words, fetched from the inquiry box (they never go through Firebase). */
    private fun fetch(c: Context, chat: Long): Call = runBlocking {
        withTimeoutOrNull(5_000) {
            try { Call.of(TeamApp.of(c).api.chat(chat)) } catch (e: Exception) { null }
        }
    } ?: Call(chat, "A traveller", "", "", "", "Open the app to read and answer.", "")

    /** a new chat: the call (or the test call) */
    private fun ring(c: Context, call: Call) {
        if (TeamApp.inFront) {
            // the app is open: its call screen at once, with the ring but without Android's banner over it
            post(c, call.chat, call.title, call.message, RING_HERE, insistent = true)
            c.startActivity(call.intent(c).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } else {
            post(c, call.chat, call.title, call.message, RING, call)
        }
        if (call.chat > 0) later(c, call)
    }

    /** someone opened or answered that chat (here or on another phone) */
    fun hush(c: Context, chat: Long) {
        NotificationManagerCompat.from(c).cancel(TAG, chat.toInt())
        c.getSystemService(AlarmManager::class.java).cancel(quietIntent(c, Call(chat, "", "", "", "", "", "")))
        _ended.tryEmit(chat)
    }

    /** "Later" on the call: this phone stops ringing, and a quiet reminder stays. The other phones keep ringing. */
    fun later(c: Context, chat: Long, title: String, text: String) {
        c.getSystemService(AlarmManager::class.java).cancel(quietIntent(c, Call(chat, "", "", "", "", "", "")))
        if (chat == 0L) NotificationManagerCompat.from(c).cancel(TAG, 0)
        else if (ringing(c, chat)) post(c, chat, title, "Still waiting: $text", QUIET)
        _ended.tryEmit(chat)
    }

    /** after two minutes, if nobody has looked, the ring stops and a quiet reminder stays */
    fun quiet(c: Context, chat: Long, title: String, text: String) {
        if (ringing(c, chat)) post(c, chat, title, "Still waiting: $text", QUIET)
        _ended.tryEmit(chat)
    }

    private fun later(c: Context, call: Call) {
        c.getSystemService(AlarmManager::class.java)
            .set(AlarmManager.ELAPSED_REALTIME, SystemClock.elapsedRealtime() + RING_FOR_MS, quietIntent(c, call))
    }

    private fun quietIntent(c: Context, call: Call): PendingIntent = PendingIntent.getBroadcast(
        c, call.chat.toInt(),
        Intent(c, QuietReceiver::class.java).putExtra("chat", call.chat).putExtra("title", call.title).putExtra("text", call.message),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    /** whether a ring for that chat is still showing */
    fun ringing(c: Context, chat: Long): Boolean =
        c.getSystemService(NotificationManager::class.java).activeNotifications
            .any { it.tag == TAG && it.id == chat.toInt() && it.notification.channelId in RINGS }

    /** the chat that is ringing right now, if any (0 = none): opening the app goes straight to it */
    fun ringingChat(c: Context): Long =
        c.getSystemService(NotificationManager::class.java).activeNotifications
            .firstOrNull { it.tag == TAG && it.id > 0 && it.notification.channelId in RINGS }?.id?.toLong() ?: 0L

    @SuppressLint("MissingPermission") // checked: areNotificationsEnabled
    private fun post(c: Context, chat: Long, title: String, text: String, channel: String, call: Call? = null, insistent: Boolean = call != null) {
        val nm = NotificationManagerCompat.from(c)
        if (!nm.areNotificationsEnabled()) return
        val open = PendingIntent.getActivity(
            c, chat.toInt(), MainActivity.openChat(c, chat),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val b = NotificationCompat.Builder(c, channel)
            .setSmallIcon(R.drawable.ic_notify)
            .setColor(BLUE)
            .setContentTitle(title)
            .setContentText(text)
            .setContentIntent(open)
            .setAutoCancel(true)
            .setPriority(if (channel == QUIET) NotificationCompat.PRIORITY_LOW else NotificationCompat.PRIORITY_HIGH)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setShowWhen(true)
        if (call != null) {
            // a call: Answer opens the chat, Decline means "later" on this phone; the call screen takes over a
            // locked or sleeping phone
            val screen = PendingIntent.getActivity(c, 10_000 + chat.toInt(), call.intent(c),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            val decline = PendingIntent.getBroadcast(c, 20_000 + chat.toInt(), call.laterIntent(c),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            val who = Person.Builder().setName(call.title).setImportant(true).build()
            b.setStyle(NotificationCompat.CallStyle.forIncomingCall(who, decline, if (chat > 0) open else decline))
                .setCategory(NotificationCompat.CATEGORY_CALL)
                .setFullScreenIntent(screen, true)
                .setOngoing(true)
        } else {
            b.setStyle(NotificationCompat.BigTextStyle().bigText(text)).setCategory(NotificationCompat.CATEGORY_MESSAGE)
        }
        if (chat == 0L && insistent) b.setTimeoutAfter(15_000) // the test ring stops by itself
        val n = b.build()
        if (insistent) n.flags = n.flags or Notification.FLAG_INSISTENT // the sound repeats until someone looks
        nm.notify(TAG, chat.toInt(), n)
    }
}
