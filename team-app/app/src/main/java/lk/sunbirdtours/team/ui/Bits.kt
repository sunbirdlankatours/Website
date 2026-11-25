package lk.sunbirdtours.team.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import lk.sunbirdtours.team.data.Chat
import lk.sunbirdtours.team.data.Message
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.cos
import kotlin.math.sin

private val zone: ZoneId get() = ZoneId.systemDefault()
private val clockFmt = DateTimeFormatter.ofPattern("h:mm a", Locale.ENGLISH)
private val dayFmt = DateTimeFormatter.ofPattern("EEE", Locale.ENGLISH)
private val dateFmt = DateTimeFormatter.ofPattern("d MMM", Locale.ENGLISH)
private val longDateFmt = DateTimeFormatter.ofPattern("EEEE d MMMM", Locale.ENGLISH)

/** "11:40 am" */
fun clock(i: Instant): String = clockFmt.format(i.atZone(zone)).lowercase(Locale.ENGLISH)

/** for the list: "now", "5 min", "11:40 am", "Yesterday", "Mon", "12 Nov" */
fun shortWhen(i: Instant, now: Instant = Instant.now()): String {
    val mins = Duration.between(i, now).toMinutes()
    if (mins < 1) return "now"
    if (mins < 60) return "$mins min"
    val d = i.atZone(zone).toLocalDate()
    val today = LocalDate.now(zone)
    return when {
        d == today -> clock(i)
        d == today.minusDays(1) -> "Yesterday"
        d.isAfter(today.minusDays(7)) -> dayFmt.format(d)
        else -> dateFmt.format(d)
    }
}

/** for the day lines in a chat: "Today", "Yesterday", "Monday 24 November" */
fun dayName(i: Instant): String {
    val d = i.atZone(zone).toLocalDate()
    val today = LocalDate.now(zone)
    return when (d) {
        today -> "Today"
        today.minusDays(1) -> "Yesterday"
        else -> longDateFmt.format(d)
    }
}

fun sameDay(a: Instant, b: Instant): Boolean = a.atZone(zone).toLocalDate() == b.atZone(zone).toLocalDate()

/** the chat as text, for an email to the traveller */
fun transcript(chat: Chat, messages: List<Message>): String = buildString {
    append("Our chat on the Sunbird Lanka Tours website:\n\n")
    for (m in messages) {
        append(if (m.fromTeam) m.name.ifBlank { "Sunbird team" } else chat.name.ifBlank { "You" })
        append(" (").append(dayName(m.at)).append(", ").append(clock(m.at)).append("):\n")
        append(m.text).append("\n\n")
    }
}

/** the yellow sun, as on the website's chat button */
@Composable
fun Sun(size: Dp, modifier: Modifier = Modifier, color: Color = Yellow) {
    Canvas(modifier.size(size)) {
        val c = Offset(this.size.width / 2, this.size.height / 2)
        val r = this.size.minDimension / 2
        drawCircle(color, radius = r * 0.42f, center = c)
        for (k in 0 until 8) {
            val a = Math.toRadians(k * 45.0)
            val from = Offset(c.x + (r * 0.6f * cos(a)).toFloat(), c.y + (r * 0.6f * sin(a)).toFloat())
            val to = Offset(c.x + (r * 0.92f * cos(a)).toFloat(), c.y + (r * 0.92f * sin(a)).toFloat())
            drawLine(color, from, to, strokeWidth = r * 0.14f, cap = StrokeCap.Round)
        }
    }
}

val Gap = 16.dp
