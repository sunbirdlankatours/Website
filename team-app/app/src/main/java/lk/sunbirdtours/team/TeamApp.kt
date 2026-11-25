package lk.sunbirdtours.team

import android.app.Application
import android.content.Context
import android.util.Log
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import lk.sunbirdtours.team.data.Api
import lk.sunbirdtours.team.data.Live
import lk.sunbirdtours.team.data.Store
import lk.sunbirdtours.team.ring.Rings
import kotlin.coroutines.resume

/**
 * The Sunbird team app. A traveller writes in the chat card on the website; the inquiry box (worker/ in the
 * website's folder) rings every team phone through Firebase; the team answers here. Sign-in is the same email
 * and password as the admin panel.
 */
class TeamApp : Application() {
    lateinit var store: Store
    lateinit var api: Api
    lateinit var live: Live
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    override fun onCreate() {
        super.onCreate()
        store = Store(this)
        api = Api(store)
        live = Live(api, store)
        Rings.channels(this)
        startFirebase()
    }

    /** Whether this version of the app was built with the Firebase file, so it can ring. */
    val ringsBuilt: Boolean get() = BuildConfig.FB_APP_ID.isNotEmpty()

    private fun startFirebase() {
        if (!ringsBuilt || FirebaseApp.getApps(this).isNotEmpty()) return
        FirebaseApp.initializeApp(
            this,
            FirebaseOptions.Builder()
                .setApplicationId(BuildConfig.FB_APP_ID)
                .setApiKey(BuildConfig.FB_API_KEY)
                .setProjectId(BuildConfig.FB_PROJECT_ID)
                .setGcmSenderId(BuildConfig.FB_SENDER_ID)
                .build(),
        )
    }

    /** Tells the inquiry box this phone's ring address (its Firebase token), so it rings for chats. */
    fun registerPhone(token: String? = null) {
        if (!ringsBuilt || store.token == null) return
        scope.launch {
            try {
                val t = token ?: firebaseToken() ?: return@launch
                api.addPhone(t)
                store.phoneToken = t
            } catch (e: Exception) {
                Log.w(TAG, "Couldn't set this phone to ring", e)
            }
        }
    }

    private suspend fun firebaseToken(): String? = suspendCancellableCoroutine { c ->
        FirebaseMessaging.getInstance().token.addOnCompleteListener { t ->
            c.resume(if (t.isSuccessful) t.result else null)
        }
    }

    companion object {
        const val TAG = "SunbirdTeam"
        fun of(c: Context) = c.applicationContext as TeamApp

        /** The chat open on screen (0 = none), and whether the app is in front: no ding for what's being read. */
        @Volatile var viewing = 0L
        @Volatile var inFront = false
    }
}
