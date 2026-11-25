package lk.sunbirdtours.team.ring

import android.app.ActivityManager
import android.app.NotificationManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.core.app.NotificationManagerCompat
import lk.sunbirdtours.team.BuildConfig

/**
 * What this phone needs so SunBird rings even when the app is closed, and the Android pages that set each one.
 * Many phones (ZTE, Xiaomi, Oppo, Vivo, Tecno…) stop an app completely when it is swiped away from the recent
 * apps, and then Firebase can't reach it. Famous apps like WhatsApp are on the phone maker's own list; SunBird has
 * to be allowed by hand, once. The "Set up this phone" card (ui/Setup.kt) walks through these.
 */
object Phone {
    fun notificationsOn(c: Context): Boolean = NotificationManagerCompat.from(c).areNotificationsEnabled()

    /** Android's battery saver leaves SunBird alone ("Unrestricted") */
    fun batteryFree(c: Context): Boolean =
        c.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(c.packageName)

    /** someone set "Background usage: restricted" for SunBird in Android's settings */
    fun backgroundBlocked(c: Context): Boolean =
        Build.VERSION.SDK_INT >= 28 && c.getSystemService(ActivityManager::class.java).isBackgroundRestricted

    /** the chat ring still has its sound (someone may have turned it down in Android's settings) */
    fun ringSoundOn(c: Context): Boolean {
        val ch = c.getSystemService(NotificationManager::class.java).getNotificationChannel(Rings.RING) ?: return true
        return ch.importance >= NotificationManager.IMPORTANCE_DEFAULT
    }

    /** phone makers whose own battery saver stops swiped-away apps unless they may auto-start */
    private val STRICT = listOf(
        "zte", "nubia", "xiaomi", "redmi", "poco", "oppo", "realme", "oneplus", "vivo", "iqoo", "huawei", "honor",
        "tecno", "infinix", "itel", "transsion", "meizu", "asus", "letv", "leeco", "lenovo", "wiko", "blackview",
        "ulefone", "oukitel", "doogee", "umidigi",
    )

    val maker: String get() = Build.MANUFACTURER.replaceFirstChar { it.uppercase() }

    /** whether to show the auto-start step (the app can't check it, so the team taps Done) */
    val strictMaker: Boolean
        get() = BuildConfig.SHOW_AUTOSTART || Build.MANUFACTURER.lowercase().let { m -> STRICT.any { m.contains(it) } }

    /** Android's own question: "Let SunBird always run in the background?" */
    fun askBattery(c: Context) {
        val ask = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + c.packageName))
        if (!start(c, ask)) start(c, Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) || start(c, appInfo(c))
    }

    /** the phone maker's auto-start page if there is a known one, otherwise SunBird's own page in Settings */
    fun openAutoStart(c: Context) {
        for ((pkg, cls) in AUTOSTART) {
            if (start(c, Intent().setComponent(ComponentName(pkg, cls)))) return
        }
        start(c, appInfo(c))
    }

    fun openAppInfo(c: Context) { start(c, appInfo(c)) }

    fun openRingSound(c: Context) {
        start(
            c, Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE, c.packageName)
                .putExtra(Settings.EXTRA_CHANNEL_ID, Rings.RING),
        )
    }

    fun openNotifications(c: Context) {
        start(c, Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, c.packageName))
    }

    fun openFullScreenCalls(c: Context) {
        if (Build.VERSION.SDK_INT >= 34) {
            start(c, Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, Uri.parse("package:" + c.packageName)))
        }
    }

    private fun appInfo(c: Context) = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + c.packageName))

    private fun start(c: Context, i: Intent): Boolean = try {
        c.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        true
    } catch (e: Exception) { // not on this phone, or the maker doesn't let other apps open it
        false
    }

    // the auto-start pages phone makers are known to have (tried in turn; most phones have none of them)
    private val AUTOSTART = listOf(
        "com.zte.heartyservice" to "com.zte.heartyservice.autorun.AppAutoRunManager",
        "com.miui.securitycenter" to "com.miui.permcenter.autostart.AutoStartManagementActivity",
        "com.coloros.safecenter" to "com.coloros.safecenter.permission.startup.StartupAppListActivity",
        "com.coloros.safecenter" to "com.coloros.safecenter.startupapp.StartupAppListActivity",
        "com.oppo.safe" to "com.oppo.safe.permission.startup.StartupAppListActivity",
        "com.vivo.permissionmanager" to "com.vivo.permissionmanager.activity.BgStartUpManagerActivity",
        "com.iqoo.secure" to "com.iqoo.secure.ui.phoneoptimize.AddWhiteListActivity",
        "com.huawei.systemmanager" to "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity",
        "com.huawei.systemmanager" to "com.huawei.systemmanager.optimize.process.ProtectActivity",
        "com.hihonor.systemmanager" to "com.hihonor.systemmanager.startupmgr.ui.StartupNormalAppListActivity",
        "com.transsion.phonemaster" to "com.cyin.himgr.autostart.AutoStartActivity",
        "com.asus.mobilemanager" to "com.asus.mobilemanager.entry.FunctionActivity",
        "com.letv.android.letvsafe" to "com.letv.android.letvsafe.AutobootManageActivity",
    )
}
