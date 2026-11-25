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

/** A trip letter or enquiry form from the website (worker/src/index.js), as the admin panel's Inquiries shows it. */
data class Inquiry(
    val id: Long,
    val created: Instant,
    val status: String,       // new | replied | booked | closed
    val name: String,
    val email: String,
    val phone: String,
    val tour: String,
    val subject: String,
    val data: Map<String, String>, // everything the form sent: travellers, dates, interests, message, page…
    val note: String,         // the team's own note
    val sentFrom: String,     // two letters, from Cloudflare
    val updated: Instant,
    val updatedBy: String,
) {
    val isNew: Boolean get() = status == "new"

    /** one thing the form sent, or "" */
    fun d(key: String): String = data[key].orEmpty().trim()

    /** "Ella & hill country · 10 days · March", like the admin panel's list */
    val headline: String
        get() = listOf(
            d("tour").ifBlank { tour }.ifBlank { subject }.ifBlank { if (d("form") == "Letter") "Trip plan" else "Enquiry" },
            daysText(d("days")),
            d("arrival").ifBlank { d("arrival_date") },
        ).filter { it.isNotBlank() }.joinToString(" · ")

    val message: String get() = d("message")

    val travellers: String
        get() = d("travellers").ifBlank {
            val adults = d("adults").toIntOrNull() ?: 0
            val children = d("children").toIntOrNull() ?: 0
            listOfNotNull(
                adults.takeIf { it > 0 }?.let { if (it == 1) "1 adult" else "$it adults" },
                children.takeIf { it > 0 }?.let { if (it == 1) "1 child" else "$it children" },
            ).joinToString(", ")
        }

    /** the phone number as WhatsApp wants it (digits with the country code), or "" (as the admin panel's waDigits) */
    val whatsapp: String
        get() {
            val digits = phone.replace(Regex("[^\\d+]"), "").replace(Regex("^00"), "+").filter { it.isDigit() }
            return if (digits.length >= 8) digits else ""
        }

    val flag: String
        get() = if (sentFrom.length == 2 && sentFrom.all { it in 'A'..'Z' }) {
            sentFrom.map { String(Character.toChars(0x1F1E6 + (it - 'A'))) }.joinToString("")
        } else ""
}

data class InquiryList(val items: List<Inquiry>, val counts: Map<String, Int>) {
    val fresh: Int get() = counts["new"] ?: 0
}

/** "10 days" from "10"; anything else as it was typed */
fun daysText(v: String): String = if (v.matches(Regex("\\d+"))) (if (v == "1") "1 day" else "$v days") else v

internal fun JSONObject.toInquiry(): Inquiry {
    val d = optJSONObject("data")
    val data = buildMap { d?.keys()?.forEach { k -> val v = d.opt(k); if (v != null && v != JSONObject.NULL) put(k, v.toString()) } }
    return Inquiry(
        id = getLong("id"),
        created = instant(optString("created")),
        status = optString("status", "new"),
        name = optString("name"),
        email = optString("email"),
        phone = optString("phone"),
        tour = optString("tour"),
        subject = optString("subject"),
        data = data,
        note = optString("note"),
        sentFrom = optString("sent_from"),
        updated = instant(optString("updated")),
        updatedBy = optString("updated_by"),
    )
}
