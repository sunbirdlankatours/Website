package lk.sunbirdtours.team.ui

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import lk.sunbirdtours.team.TeamApp
import lk.sunbirdtours.team.ring.Phone
import lk.sunbirdtours.team.ring.Rings

/** One thing this phone needs to ring with SunBird closed: done, or a button (and maybe a second one) to do it. */
private class Step(
    val title: String,
    val why: String,
    val done: Boolean,
    val action: String,
    val go: () -> Unit,
    val second: Pair<String, () -> Unit>? = null,
)

/**
 * "Set up this phone": what it still needs so SunBird rings even when it's closed (ring/Phone.kt), each with a
 * button to the right Android page. Done steps get a tick; the card goes once everything is done. It checks again
 * every time the team member comes back from Android's settings.
 */
@Composable
fun SetupCard(m: TeamModel) {
    val ctx = LocalContext.current
    val team = TeamApp.of(ctx)
    var check by remember { mutableIntStateOf(0) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { check++ }
    var fromButton by remember { mutableStateOf(false) }
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        check++
        if (!granted && fromButton) Phone.openNotifications(ctx) // said no before: Android won't ask again, so the settings
    }
    LaunchedEffect(Unit) { // the first time: Android's own question about notifications
        if (!Phone.notificationsOn(ctx) && Build.VERSION.SDK_INT >= 33) ask.launch(Manifest.permission.POST_NOTIFICATIONS)
    }
    var autoDone by remember { mutableStateOf(team.store.autoStartDone) }

    if (!team.ringsBuilt) {
        Note("This version of the app can't ring: it was built without the Firebase file.", null) {}
        return
    }

    val steps = remember(check, autoDone) {
        val notifications = Phone.notificationsOn(ctx)
        buildList {
            add(Step("Notifications", "So chats and inquiries can ring and show on this phone.", notifications, "Allow", {
                fromButton = true
                if (Build.VERSION.SDK_INT >= 33) ask.launch(Manifest.permission.POST_NOTIFICATIONS) else Phone.openNotifications(ctx)
            }))
            add(Step(
                "Run in the background", "So it still rings after SunBird is swiped away or the phone has been asleep.",
                Phone.batteryFree(ctx), "Allow", { Phone.askBattery(ctx) },
            ))
            if (Phone.backgroundBlocked(ctx)) add(Step(
                "Background use is blocked", "On the page that opens, set SunBird's battery or background use to allowed.",
                false, "Fix", { Phone.openAppInfo(ctx) },
            ))
            if (Phone.strictMaker) add(Step(
                "Auto-start", "${Phone.maker} phones stop apps that are swiped away. Tap Open, allow SunBird to auto-start " +
                    "or run in the background, then come back and tap Done.",
                autoDone, "Open", { Phone.openAutoStart(ctx) },
                second = "Done" to { team.store.autoStartDone = true; autoDone = true },
            ))
            if (Build.VERSION.SDK_INT >= 34) add(Step(
                "Full-screen calls", "So a new chat shows like a phone call when the phone is locked.",
                Rings.canTakeOverScreen(ctx), "Allow", { Phone.openFullScreenCalls(ctx) },
            ))
            if (notifications) add(Step(
                "Ring sound", "The chat ring has been turned down in Android's settings. Turn its sound back on.",
                Phone.ringSoundOn(ctx), "Turn on", { Phone.openRingSound(ctx) },
            ))
        }
    }
    val left = steps.count { !it.done }
    if (left == 0) return

    Surface(color = Pale, shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth().padding(horizontal = Gap, vertical = 6.dp)) {
        Column(Modifier.padding(start = 16.dp, end = 8.dp, top = 14.dp, bottom = 4.dp)) {
            Text("Set up this phone so it always rings", fontWeight = FontWeight.SemiBold, color = Navy, fontSize = 15.sp)
            Spacer(Modifier.height(2.dp))
            Text(
                (if (left == 1) "1 step left. " else "$left steps left. ") +
                    "Phones stop apps in the background unless they're allowed, the way WhatsApp is.",
                fontSize = 12.sp, color = Muted, lineHeight = 16.sp, modifier = Modifier.padding(end = 8.dp),
            )
            Spacer(Modifier.height(6.dp))
            for (s in steps) StepRow(s)
            TextButton(
                onClick = { m.testRing(20) }, enabled = Phone.notificationsOn(ctx),
                modifier = Modifier.padding(start = 26.dp),
            ) { Text("Test with the app closed", fontWeight = FontWeight.Bold) }
        }
    }
}

@Composable
private fun StepRow(s: Step) {
    Row(Modifier.fillMaxWidth().padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
        if (s.done) Icon(Icons.Filled.CheckCircle, contentDescription = "Done", tint = Blue, modifier = Modifier.size(20.dp))
        else Box(Modifier.size(20.dp).padding(1.dp).border(2.dp, Navy.copy(alpha = 0.35f), CircleShape))
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(s.title, fontWeight = FontWeight.SemiBold, fontSize = 14.sp, color = if (s.done) Muted else Navy)
            if (!s.done) Text(s.why, fontSize = 12.sp, color = Muted, lineHeight = 16.sp)
        }
        if (!s.done) {
            Spacer(Modifier.width(6.dp))
            Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Button(
                    onClick = s.go, shape = RoundedCornerShape(48.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Yellow, contentColor = Navy),
                    contentPadding = ButtonDefaults.TextButtonContentPadding,
                    modifier = Modifier.height(36.dp),
                ) { Text(s.action, fontWeight = FontWeight.Bold, fontSize = 13.sp) }
                s.second?.let { (label, go) -> TextButton(onClick = go, modifier = Modifier.height(34.dp)) { Text(label, fontSize = 13.sp) } }
            }
        }
    }
}
