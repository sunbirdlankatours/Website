package lk.sunbirdtours.team.data

import org.json.JSONObject
import java.time.Instant
import java.util.Locale

/** The team member signed in on this phone. */
data class Me(val id: Long, val name: String, val email: String) {
    val firstName: String get() = name.trim().split(Regex("\\s+")).firstOrNull()?.takeIf { it.isNotBlank() } ?: "Sunbird team"
}

/** One chat with a traveller, as the list shows it. */
data class Chat(
    val id: Long,
    val created: Instant,
    val updated: Instant,
    val status: String,       // open | closed
    val name: String,         // the traveller's, if they gave it
    val email: String,
    val whatsapp: String,
    val page: String,         // where on the website they are writing from
    val country: String,      // two letters, from Cloudflare
    val member: Long,         // who on the team is answering (0 = nobody yet)
    val memberName: String,
    val lastText: String,
    val lastFrom: String,     // visitor | team
    val unread: Int,          // the traveller's messages since the team last read it
) {
    val waiting: Boolean get() = status == "open" && unread > 0

    val countryName: String
        get() = if (country.length == 2) Locale("", country).getDisplayCountry(Locale.ENGLISH) else ""

    /** "Sam", or "Traveller from Germany", or "Traveller 12" */
    val title: String
        get() = name.ifBlank { if (countryName.isNotBlank()) "Traveller from $countryName" else "Traveller $id" }

    /** the country's flag, from its two letters */
    val flag: String
        get() = if (country.length == 2 && country.all { it in 'A'..'Z' }) {
            country.map { String(Character.toChars(0x1F1E6 + (it - 'A'))) }.joinToString("")
        } else ""
}

/** One message in a chat. who: visitor (the traveller) or team. */
data class Message(val id: Long, val at: Instant, val who: String, val member: Long, val name: String, val text: String) {
    val fromTeam: Boolean get() = who == "team"
}

data class ChatList(val items: List<Chat>, val waiting: Int)
data class ChatDetail(val chat: Chat, val messages: List<Message>)

internal fun instant(s: String?): Instant = try { Instant.parse(s) } catch (e: Exception) { Instant.EPOCH }

internal fun JSONObject.toChat() = Chat(
    id = getLong("id"),
    created = instant(optString("created")),
    updated = instant(optString("updated")),
    status = optString("status", "open"),
    name = optString("name"),
    email = optString("email"),
    whatsapp = optString("whatsapp"),
    page = optString("page"),
    country = optString("country"),
    member = optLong("member"),
    memberName = optString("member_name"),
    lastText = optString("last_text"),
    lastFrom = optString("last_from"),
    unread = optInt("unread"),
)

internal fun JSONObject.toMessage() = Message(
    id = getLong("id"),
    at = instant(optString("at")),
    who = optString("who"),
    member = optLong("member"),
    name = optString("name"),
    text = optString("text"),
)
