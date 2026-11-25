package lk.sunbirdtours.team.data

import android.content.Context

/** The sign-in, kept on this phone only (the app is not backed up). */
class Store(context: Context) {
    private val p = context.getSharedPreferences("sign-in", Context.MODE_PRIVATE)

    /** the sign-in pass from the inquiry box (lasts 30 days) */
    val token: String? get() = p.getString("token", null)

    /** this phone's ring address, as last told to the inquiry box */
    var phoneToken: String?
        get() = p.getString("phone", null)
        set(v) { p.edit().putString("phone", v).apply() }

    fun me(): Me? {
        if (token == null) return null
        return Me(p.getLong("id", 0), p.getString("name", "") ?: "", p.getString("email", "") ?: "")
    }

    fun signedIn(token: String, me: Me) {
        p.edit().putString("token", token).putLong("id", me.id).putString("name", me.name)
            .putString("email", me.email).commit()
    }

    fun clear() {
        p.edit().clear().commit()
    }
}
