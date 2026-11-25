package lk.sunbirdtours.team.ring

import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import lk.sunbirdtours.team.TeamApp

/**
 * Firebase wakes the phone here when the inquiry box rings it. The ring carries only its kind and the chat's
 * number; Rings fetches the traveller's words from the inquiry box itself.
 */
class RingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        TeamApp.of(this).registerPhone(token) // the ring address changed: tell the inquiry box
    }

    override fun onMessageReceived(message: RemoteMessage) {
        if (TeamApp.of(this).store.token == null) return // signed out on this phone
        val kind = message.data["kind"] ?: return
        Rings.handle(this, kind, message.data["chat"]?.toLongOrNull() ?: 0L)
    }
}
