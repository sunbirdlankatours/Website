import groovy.json.JsonSlurper
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

// The inquiry box the app talks to. To try the app against one on this computer (from the emulator):
//   gradlew assembleDebug -Psunbird.api=http://10.0.2.2:8787
val apiBase = (findProperty("sunbird.api") as String?)
    ?: "https://green-sea-c14dsunbird-inquiries.sunbirdlankatours.workers.dev"

// Firebase, which wakes the phone to ring: the google-services.json from the Firebase console (Project settings
// → Your apps → the Android app lk.sunbirdtours.team), put in this folder (app/). It is read here rather than by
// Google's plugin. Without it the app works, but nothing rings.
val firebase: Map<String, String> = run {
    val f = file("google-services.json")
    if (!f.exists()) return@run emptyMap()
    @Suppress("UNCHECKED_CAST")
    val j = JsonSlurper().parse(f) as Map<String, Any?>
    val info = j["project_info"] as Map<String, Any?>
    val clients = j["client"] as List<Map<String, Any?>>
    val mine = clients.firstOrNull {
        val ci = it["client_info"] as Map<String, Any?>
        (ci["android_client_info"] as Map<String, Any?>)["package_name"] == "lk.sunbirdtours.team"
    } ?: error("google-services.json has no Android app called lk.sunbirdtours.team. Add one in the Firebase console.")
    val keys = mine["api_key"] as List<Map<String, Any?>>
    mapOf(
        "FB_APP_ID" to ((mine["client_info"] as Map<String, Any?>)["mobilesdk_app_id"] as String),
        "FB_API_KEY" to (keys.first()["current_key"] as String),
        "FB_PROJECT_ID" to (info["project_id"] as String),
        "FB_SENDER_ID" to (info["project_number"] as String),
    )
}

// The key the app is signed with (keystore/, made once, kept off GitHub). Every new version must be signed with
// the same key, or phones refuse it as an update. Back it up.
val keyProps = Properties().apply {
    val f = rootProject.file("keystore.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "lk.sunbirdtours.team"
    compileSdk = 36

    defaultConfig {
        applicationId = "lk.sunbirdtours.team"
        minSdk = 26
        targetSdk = 36
        versionCode = 4
        versionName = "1.3"
        buildConfigField("String", "API_BASE", "\"$apiBase\"")
        // -Psunbird.autostart shows the phone-maker auto-start step on any phone (for trying it on the emulator)
        buildConfigField("boolean", "SHOW_AUTOSTART", if (findProperty("sunbird.autostart") != null) "true" else "false")
        for (k in listOf("FB_APP_ID", "FB_API_KEY", "FB_PROJECT_ID", "FB_SENDER_ID")) {
            buildConfigField("String", k, "\"${firebase[k] ?: ""}\"")
        }
    }

    signingConfigs {
        if (keyProps.getProperty("storeFile") != null) {
            create("release") {
                storeFile = rootProject.file(keyProps.getProperty("storeFile"))
                storePassword = keyProps.getProperty("storePassword")
                keyAlias = keyProps.getProperty("keyAlias")
                keyPassword = keyProps.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfigs.findByName("release")?.let { signingConfig = it }
            manifestPlaceholders["cleartext"] = "false"
        }
        debug {
            manifestPlaceholders["cleartext"] = "true" // http to the inquiry box on this computer, for testing
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.activity:activity-compose:1.12.2")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation(platform("com.google.firebase:firebase-bom:34.0.0"))
    implementation("com.google.firebase:firebase-messaging")
}
