package lk.sunbirdtours.team.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import lk.sunbirdtours.team.R
import lk.sunbirdtours.team.data.Inquiry
import lk.sunbirdtours.team.data.daysText

/** the statuses an inquiry can have, as the admin panel names them */
private val STATUSES = listOf("new" to "New", "replied" to "Replied", "booked" to "Booked", "closed" to "Closed")

/** a status's colours: background, words */
private fun statusColors(s: String): Pair<Color, Color> = when (s) {
    "new" -> Yellow to Navy
    "replied" -> Color(0xFFDCEBF7) to Blue
    "booked" -> Color(0xFFE2F1E4) to Color(0xFF2E6B3A)
    else -> Color(0xFFEEF1F2) to Muted
}

/** The Inquiries tab: trip letters and enquiry forms from the website, newest first, like the admin panel's. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InquiriesScreen(m: TeamModel, bar: SnackbarHostState) {
    Scaffold(
        snackbarHost = { SnackbarHost(bar) },
        contentWindowInsets = WindowInsets(0, 0, 0, 0), // the tabs at the bottom take care of the bottom edge
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Inquiries", fontWeight = FontWeight.SemiBold, color = Navy)
                        val n = m.newInquiries
                        Text(
                            when (n) { 0 -> "Nothing new"; 1 -> "1 new"; else -> "$n new" },
                            style = MaterialTheme.typography.bodySmall, color = Muted,
                        )
                    }
                },
                actions = { IconButton(onClick = { m.refreshInquiries() }) { Icon(Icons.Filled.Refresh, contentDescription = "Refresh") } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Paper),
            )
        },
    ) { pad ->
        Column(Modifier.fillMaxSize().padding(pad)) {
            SetupCard(m)
            Row(
                Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = Gap, vertical = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                for ((k, label) in STATUSES + ("all" to "All")) {
                    val n = if (k == "all") m.inquiryCounts.values.sum() else m.inquiryCounts[k] ?: 0
                    FilterChip(
                        selected = m.inquiryFilter == k, onClick = { m.inquiryFilter = k },
                        label = { Text(if (n > 0) "$label  $n" else label) },
                        colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Color(0xFFDCEBF7), selectedLabelColor = Navy),
                    )
                }
            }
            val shown = if (m.inquiryFilter == "all") m.inquiries else m.inquiries.filter { it.status == m.inquiryFilter }
            PullToRefreshBox(isRefreshing = m.inquiriesLoading, onRefresh = { m.refreshInquiries() }, modifier = Modifier.fillMaxSize()) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
                    if (shown.isEmpty() && !m.inquiriesLoading) item { NoInquiries(m.inquiryFilter) }
                    items(shown, key = { it.id }) { q ->
                        InquiryRow(q) { m.openInquiry(q.id) }
                        HorizontalDivider(Modifier.padding(start = 78.dp), color = Line)
                    }
                }
            }
        }
    }
}

@Composable
private fun InquiryRow(q: Inquiry, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = Gap, vertical = 12.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Box(
            Modifier.size(46.dp).clip(CircleShape).background(if (q.isNew) Yellow else Color(0xFFDCEBF7)),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                q.flag.ifBlank { q.name.trim().take(1).uppercase().ifBlank { "?" } },
                fontSize = if (q.flag.isNotBlank()) 22.sp else 18.sp, color = Navy, fontWeight = FontWeight.SemiBold,
            )
        }
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    q.name.ifBlank { "Traveller" }, Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis,
                    fontWeight = if (q.isNew) FontWeight.Bold else FontWeight.SemiBold, color = Ink, fontSize = 16.sp,
                )
                Text(shortWhen(q.created), style = MaterialTheme.typography.bodySmall, color = if (q.isNew) Blue else Muted)
            }
            Spacer(Modifier.height(3.dp))
            Text(q.headline, fontSize = 14.sp, color = if (q.isNew) Ink else Muted, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (q.message.isNotBlank()) {
                Spacer(Modifier.height(2.dp))
                Text(q.message, fontSize = 13.sp, color = Muted, maxLines = 2, overflow = TextOverflow.Ellipsis, lineHeight = 18.sp)
            }
            if (!q.isNew) {
                Spacer(Modifier.height(6.dp))
                Pill(q.status)
            }
        }
    }
}

@Composable
private fun Pill(status: String) {
    val (bg, ink) = statusColors(status)
    Text(
        STATUSES.firstOrNull { it.first == status }?.second ?: status,
        Modifier.clip(RoundedCornerShape(48.dp)).background(bg).padding(horizontal = 10.dp, vertical = 3.dp),
        color = ink, fontSize = 11.sp, fontWeight = FontWeight.Bold,
    )
}

@Composable
private fun NoInquiries(filter: String) {
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 36.dp, vertical = 56.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Image(painterResource(R.drawable.logo_emblem), contentDescription = null, Modifier.size(64.dp).alpha(0.45f))
        val label = STATUSES.firstOrNull { it.first == filter }?.second?.lowercase()
        Text(if (label == null) "No inquiries yet" else "No $label inquiries", fontWeight = FontWeight.SemiBold, color = Navy, fontSize = 17.sp)
        Text(
            if (filter == "new") "When a traveller sends a trip letter or the enquiry form on the website, this phone gets a notification and it shows here."
            else "Inquiries you mark ${label ?: ""} show here.",
            color = Muted, textAlign = TextAlign.Center, fontSize = 14.sp,
        )
    }
}

/** One inquiry: everything the traveller sent, ways to answer them, its status and the team's note. */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun InquiryScreen(m: TeamModel, bar: SnackbarHostState) {
    val ctx = LocalContext.current
    val q = m.inquiry
    Scaffold(
        snackbarHost = { SnackbarHost(bar) },
        topBar = {
            TopAppBar(
                navigationIcon = {
                    IconButton(onClick = { m.closeInquiry() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back to inquiries") }
                },
                title = {
                    Column {
                        Text(
                            if (q == null) "Inquiry" else (q.flag + " " + q.name).trim(),
                            maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.SemiBold, color = Navy,
                        )
                        if (q != null) Text(
                            dayName(q.created) + ", " + clock(q.created),
                            style = MaterialTheme.typography.bodySmall, color = Muted, maxLines = 1,
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Paper),
            )
        },
    ) { pad ->
        if (q == null) {
            Box(Modifier.fillMaxSize().padding(pad), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            return@Scaffold
        }
        Column(
            Modifier.fillMaxSize().padding(pad).imePadding().verticalScroll(rememberScrollState())
                .padding(horizontal = Gap, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text(q.headline, fontSize = 18.sp, fontWeight = FontWeight.SemiBold, color = Navy)

            // answer them
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (q.email.isNotBlank()) AssistChip(
                    onClick = { open(ctx, replyMail(q)) },
                    label = { Text("Email", maxLines = 1) },
                    leadingIcon = { Icon(Icons.Filled.Email, contentDescription = null, Modifier.size(AssistChipDefaults.IconSize)) },
                )
                if (q.whatsapp.isNotBlank()) AssistChip(
                    onClick = { open(ctx, Intent(Intent.ACTION_VIEW, Uri.parse("https://wa.me/" + q.whatsapp))) },
                    label = { Text("WhatsApp", maxLines = 1) },
                    leadingIcon = { Icon(Icons.Filled.Phone, contentDescription = null, Modifier.size(AssistChipDefaults.IconSize)) },
                )
                if (q.phone.isNotBlank()) AssistChip(
                    onClick = { open(ctx, Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + q.phone.filter { it.isDigit() || it == '+' }))) },
                    label = { Text("Call", maxLines = 1) },
                    leadingIcon = { Icon(Icons.Filled.Call, contentDescription = null, Modifier.size(AssistChipDefaults.IconSize)) },
                )
            }

            // where it stands (the number on the app icon counts the New ones)
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                STATUSES.forEachIndexed { i, (k, label) ->
                    SegmentedButton(
                        selected = q.status == k, onClick = { m.markInquiry(k) },
                        shape = SegmentedButtonDefaults.itemShape(i, STATUSES.size),
                    ) { Text(label, fontSize = 13.sp, maxLines = 1) }
                }
            }

            // the trip
            val facts = listOf(
                "Email" to q.email,
                "Phone" to q.phone,
                "Country" to q.d("country"),
                "Travellers" to q.travellers,
                "Arriving" to q.d("arrival").ifBlank { q.d("arrival_date") },
                "Length" to daysText(q.d("days")),
                "Dates" to q.d("dates"),
                "They'd love" to q.d("interests"),
                "Tour" to q.d("tour").ifBlank { q.tour },
                "Subject" to q.subject.takeIf { it != q.d("tour") }.orEmpty(),
                "Sent from" to q.d("page").replace(Regex("^https?://[^/]+"), ""),
                "Last changed" to if (q.updatedBy.isNotBlank()) q.updatedBy + " · " + shortWhen(q.updated) else "",
            ).filter { it.second.isNotBlank() }
            Surface(color = Color.White, shape = RoundedCornerShape(18.dp), border = BorderStroke(1.dp, Line)) {
                Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
                    facts.forEachIndexed { i, (label, value) ->
                        if (i > 0) HorizontalDivider(color = Line)
                        Row(Modifier.fillMaxWidth().padding(vertical = 9.dp)) {
                            Text(label, Modifier.width(118.dp), fontSize = 13.sp, color = Muted)
                            SelectionContainer(Modifier.weight(1f)) { Text(value, fontSize = 14.sp, color = Ink) }
                        }
                    }
                }
            }

            // what they wrote
            if (q.message.isNotBlank()) {
                Text("THEIR MESSAGE", fontSize = 11.sp, letterSpacing = 2.sp, color = Muted, fontWeight = FontWeight.Bold)
                Surface(color = Color.White, shape = RoundedCornerShape(18.dp), border = BorderStroke(1.dp, Line)) {
                    SelectionContainer {
                        Text(q.message, Modifier.fillMaxWidth().padding(16.dp), fontSize = 15.sp, lineHeight = 22.sp, color = Ink)
                    }
                }
            }

            // the team's own note
            var note by rememberSaveable(q.id) { mutableStateOf(q.note) }
            OutlinedTextField(
                value = note, onValueChange = { note = it },
                label = { Text("Team note") },
                placeholder = { Text("Only the team sees this. For example: sent the 10-day plan, waiting for dates.") },
                minLines = 3, shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = Color.White, unfocusedContainerColor = Color.White,
                    focusedBorderColor = Sky, unfocusedBorderColor = Line,
                ),
            )
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                Button(onClick = { m.saveInquiryNote(note) }, enabled = note != q.note, shape = RoundedCornerShape(48.dp)) {
                    Text("Save note", fontWeight = FontWeight.SemiBold)
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

/** an email back to them, started the way the admin panel starts it */
private fun replyMail(q: Inquiry): Intent {
    val first = q.name.trim().split(Regex("\\s+")).firstOrNull().orEmpty()
    val about = q.subject.ifBlank { q.d("tour").ifBlank { q.tour }.takeIf { it.isNotBlank() }?.let { "Your $it enquiry" } ?: "Your trip to Sri Lanka" }
    return Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:" + q.email))
        .putExtra(Intent.EXTRA_SUBJECT, "Re: " + about.replace(Regex("\\s+–\\s+[^–]*$"), ""))
        .putExtra(Intent.EXTRA_TEXT, "Dear $first,\n\n")
}

private fun open(ctx: Context, i: Intent) {
    try { ctx.startActivity(i) } catch (e: ActivityNotFoundException) { /* no app for it on this phone */ }
}
