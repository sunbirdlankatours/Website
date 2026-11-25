package lk.sunbirdtours.team.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import lk.sunbirdtours.team.BuildConfig
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/** A refusal or a problem, in words to show the team. signIn: the sign-in has ended. */
class ApiError(val status: Int, message: String, val signIn: Boolean = false) : Exception(message)

/** Talks to the inquiry box (worker/src/chat.js and index.js in the website's folder). */
class Api(private val store: Store) {
    val base: String = BuildConfig.API_BASE.trimEnd('/')
    val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .writeTimeout(20, TimeUnit.SECONDS)
        .build()
    private val jsonType = "application/json; charset=utf-8".toMediaType()

    private suspend fun call(method: String, path: String, body: JSONObject? = null): JSONObject = withContext(Dispatchers.IO) {
        val payload = when {
            body != null -> body.toString().toRequestBody(jsonType)
            method == "POST" || method == "PATCH" -> "{}".toRequestBody(jsonType)
            else -> null
        }
        val req = Request.Builder().url(base + path).method(method, payload)
        store.token?.let { req.header("Authorization", "Bearer $it") }
        try {
            http.newCall(req.build()).execute().use { r ->
                val text = r.body?.string().orEmpty()
                val j = try { JSONObject(text) } catch (e: JSONException) { JSONObject() }
                if (!r.isSuccessful) {
                    val said = j.optString("error").ifBlank { "The inquiry box answered ${r.code}. Please try again." }
                    throw ApiError(r.code, said, j.optBoolean("signin"))
                }
                j
            }
        } catch (e: IOException) {
            throw ApiError(0, "No connection to the inquiry box. Check the internet and try again.")
        }
    }

    suspend fun login(email: String, password: String): Me {
        val j = call("POST", "/api/login", JSONObject().put("email", email.trim()).put("password", password))
        val u = j.getJSONObject("user")
        val me = Me(u.getLong("id"), u.optString("name"), u.optString("email"))
        store.signedIn(j.getString("token"), me)
        return me
    }

    suspend fun logout() {
        call("POST", "/api/logout")
    }

    suspend fun chats(closed: Boolean): ChatList {
        val j = call("GET", "/api/chats" + if (closed) "?status=closed" else "")
        val a = j.getJSONArray("items")
        return ChatList(List(a.length()) { a.getJSONObject(it).toChat() }, j.optInt("waiting"))
    }

    suspend fun chat(id: Long, after: Long = 0): ChatDetail {
        val j = call("GET", "/api/chats?id=$id" + if (after > 0) "&after=$after" else "")
        val a = j.getJSONArray("messages")
        return ChatDetail(j.getJSONObject("chat").toChat(), List(a.length()) { a.getJSONObject(it).toMessage() })
    }

    suspend fun reply(id: Long, text: String): Message =
        call("POST", "/api/chats", JSONObject().put("id", id).put("text", text)).getJSONObject("message").toMessage()

    /** read: the other phones stop ringing for it */
    suspend fun markRead(id: Long) {
        call("PATCH", "/api/chats", JSONObject().put("id", id).put("read", true))
    }

    suspend fun setStatus(id: Long, status: String) {
        call("PATCH", "/api/chats", JSONObject().put("id", id).put("status", status))
    }

    suspend fun delete(id: Long) {
        call("DELETE", "/api/chats?id=$id")
    }

    suspend fun addPhone(token: String) {
        call("POST", "/api/devices", JSONObject().put("token", token).put("platform", "android"))
    }

    /** rings this person's phones once (after [wait] seconds, for testing with the app closed); the phones it reached */
    suspend fun testRing(wait: Int = 0): Int =
        call("POST", "/api/devices/test", JSONObject().put("wait", wait)).optInt("sent")

    /** the newest 300 inquiries from the website, and how many there are of each status */
    suspend fun inquiries(): InquiryList {
        val j = call("GET", "/api/inquiries")
        val a = j.getJSONArray("items")
        val c = j.optJSONObject("counts")
        val counts = buildMap { c?.keys()?.forEach { put(it, c.optInt(it)) } }
        return InquiryList(List(a.length()) { a.getJSONObject(it).toInquiry() }, counts)
    }

    /** marks an inquiry (new, replied, booked, closed) or saves the team's note on it */
    suspend fun changeInquiry(id: Long, status: String? = null, note: String? = null) {
        val b = JSONObject().put("id", id)
        if (status != null) b.put("status", status)
        if (note != null) b.put("note", note)
        call("PATCH", "/api/inquiries", b)
    }
}
